from datetime import datetime, timedelta, timezone

from dateutil.relativedelta import relativedelta
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from common.config.config import settings
from common.exception.lzsd_exception import ServiceWarning
from core.entity.do.membership_token_grant_plan_do import MembershipTokenGrantPlan
from core.entity.do.user_account_do import UserAccount, AccountLog
from core.entity.vo.user_vo import AccountInfoResponse
from core.enums.constants import UserLevel, BizType, ChargeType, AssetType
from core.enums.token_consume_source import TokenConsumeSource
from dao.membership_dao import MembershipDAO
from dao.membership_token_grant_plan_dao import MembershipTokenGrantPlanDAO
from dao.package_dao import PackageDAO
from dao.user_account_dao import UserAccountDAO
from service.usage_service import UsageService


class AccountService:
    """
    账户服务（发权益）
    """

    @staticmethod
    def _as_utc_naive(value: datetime) -> datetime:
        # 项目里 MySQL DateTime 和 scheduler 主要使用 naive UTC，统一后再比较，避免 aware/naive 混用报错。
        if value.tzinfo is None:
            return value

        return value.astimezone(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _split_monthly_token_allowance(total_amount: int) -> list[int]:
        # 发放策略：首发 60%，剩余 40% 分 4 周发放；最后一期兜底处理不能整除的余数。
        initial_amount = total_amount * 60 // 100
        remaining_amount = total_amount - initial_amount
        weekly_amount = remaining_amount // 4
        weekly_amounts = [weekly_amount] * 4
        weekly_amounts[-1] += remaining_amount - sum(weekly_amounts)
        return [initial_amount, *weekly_amounts]

    @staticmethod
    def _membership_cycle_count(level_code: str, duration_days: int) -> int:
        # 年会员每个月开启一轮新的月度额度周期，月会员/basic 只开启当前订单周期。
        if level_code == UserLevel.PRO_ANNUAL.value:
            return 12

        return max(1, duration_days // 30)

    @staticmethod
    def _build_membership_token_plans(
            user_id: int,
            order_no: str,
            level_code: str,
            monthly_token_allowance: int,
            duration_days: int,
            start_at: datetime,
            expire_at: datetime,
    ) -> list[MembershipTokenGrantPlan]:
        if monthly_token_allowance <= 0:
            return []

        plans = []
        cycle_count = AccountService._membership_cycle_count(level_code, duration_days)
        amounts = AccountService._split_monthly_token_allowance(monthly_token_allowance)

        for cycle_no in range(1, cycle_count + 1):
            cycle_start = start_at + relativedelta(months=cycle_no - 1)

            if cycle_no > 1:
                # 新周期开始前先清空上个周期未用完的 monthly_balance，再发本周期首期。
                plans.append(
                    MembershipTokenGrantPlan(
                        user_id=user_id,
                        order_no=order_no,
                        level_code=level_code,
                        cycle_no=cycle_no,
                        period_no=-1,
                        plan_type="RESET",
                        amount=0,
                        scheduled_at=cycle_start,
                        membership_expire_at=expire_at,
                        status="PENDING",
                        extra={"source": "membership", "reason": "monthly_cycle_reset"},
                    )
                )

            for period_no, amount in enumerate(amounts):
                # period_no=0 是首发 60%，period_no=1-4 是后续每周发放。
                plans.append(
                    MembershipTokenGrantPlan(
                        user_id=user_id,
                        order_no=order_no,
                        level_code=level_code,
                        cycle_no=cycle_no,
                        period_no=period_no,
                        plan_type="GRANT",
                        amount=amount,
                        scheduled_at=cycle_start + timedelta(days=period_no * 7),
                        membership_expire_at=expire_at,
                        status="PENDING",
                        extra={"source": "membership", "grant_mode": "60_40_weekly"},
                    )
                )

        return plans

    @staticmethod
    def _write_monthly_recharge_log(
            db: AsyncSession,
            account: UserAccount,
            biz_id: str,
            amount: int,
            level_code: str,
            extra: dict | None = None,
    ) -> None:
        log = AccountLog(
            user_id=account.user_id,
            biz_id=biz_id,
            biz_type=BizType.ORDER.value,
            change_type=ChargeType.RECHARGE.value,
            asset_type=AssetType.MONTHLY.value,
            amount=amount,
            balance_after=account.monthly_balance,
            extra={
                "source": "membership",
                "level": level_code,
                **(extra or {}),
            }
        )
        db.add(log)

    @staticmethod
    def _write_monthly_reset_log(
            db: AsyncSession,
            account: UserAccount,
            biz_id: str,
            amount: int,
            level_code: str,
            reason: str,
    ) -> None:
        if amount <= 0:
            return

        log = AccountLog(
            user_id=account.user_id,
            biz_id=biz_id,
            biz_type=BizType.SYSTEM.value,
            change_type=ChargeType.EXPIRE.value,
            asset_type=AssetType.MONTHLY.value,
            amount=-amount,
            balance_after=account.monthly_balance,
            extra={
                "level": level_code,
                "reason": reason,
            }

        )
        db.add(log)

    @staticmethod
    async def issue_membership_token_plan(
            db: AsyncSession,
            account: UserAccount,
            plan: MembershipTokenGrantPlan,
            now: datetime | None = None,
    ) -> None:
        now = now or datetime.utcnow()

        if plan.status != "PENDING":
            return

        if now > plan.membership_expire_at:
            # 计划晚于会员订单有效期时不再补发，避免过期权益继续到账。
            plan.status = "CANCELED"
            plan.issued_at = now
            plan.extra = {
                **(plan.extra or {}),
                "cancel_reason": "membership_expired",
            }
            return

        if plan.plan_type == "RESET":
            # 年会员新月周期：清掉旧月度余额，总额度同步扣回，再由后续 GRANT 计划补入新月额度。
            old_monthly = account.monthly_balance or 0
            account.monthly_balance = 0
            account.total_amount = max((account.total_amount or 0) - old_monthly, 0)
            account.last_reset_at = now

            AccountService._write_monthly_reset_log(
                db=db,
                account=account,
                biz_id=f"{plan.order_no}:cycle:{plan.cycle_no}:reset",
                amount=old_monthly,
                level_code=plan.level_code,
                reason="monthly_cycle_reset",
            )
        else:
            # 普通发放：所有会员月度权益都进入 monthly_balance，保持现有余额展示和扣费逻辑不变。
            account.monthly_balance += plan.amount
            account.total_amount += plan.amount

            AccountService._write_monthly_recharge_log(
                db=db,
                account=account,
                biz_id=f"{plan.order_no}:cycle:{plan.cycle_no}:period:{plan.period_no}",
                amount=plan.amount,
                level_code=plan.level_code,
                extra={
                    "cycle_no": plan.cycle_no,
                    "period_no": plan.period_no,
                    "grant_mode": "60_40_weekly",
                },
            )

        plan.status = "ISSUED"
        plan.issued_at = now

    @staticmethod
    def is_membership_active(account: UserAccount) -> bool:
        """
        判断会员是否有效（唯一标准入口）
        """
        if not account:
            return False

        if not account.expire_at:
            return False

        now = datetime.now(timezone.utc)

        # 兼容数据库里是 naive datetime 的情况
        expire_at = account.expire_at
        if expire_at.tzinfo is None:
            expire_at = expire_at.replace(tzinfo=timezone.utc)

        return expire_at > now

    @staticmethod
    async def get_effective_membership(db, account: UserAccount):
        """
        获取“当前有效会员”（已过期返回 None）
        """
        if not AccountService.is_membership_active(account):
            return None

        from dao.membership_dao import MembershipDAO
        return await MembershipDAO.get_by_code(db, account.level_code)

    @staticmethod
    def get_user_level(account: UserAccount) -> str:
        """
        对外统一返回用户等级（已过期自动降级为 FREE）
        """
        if not AccountService.is_membership_active(account):
            return "FREE"

        return account.level_code
    

    @staticmethod
    async def get_account_info(db: AsyncSession, user_id: int):
        """
        获取用户资产信息
        """
        # =============计算个人每天免费额度===================
        usage_service = UsageService(db)
        input_total, output_total = await usage_service._get_user_daily_input_output(user_id)
        user_already_used_weighted = int((input_total + output_total) * settings.MULTIPLIER)
        # 计算今天剩余可用的免费额度
        free_limit_remaining = max(0, settings.USER_DAILY_TOKEN_LIMIT - user_already_used_weighted)
        # ==================== 1. 获取账户 ====================
        account = await UserAccountDAO.get_active_account(db=db, user_id=user_id)
        if not account:
            # 每日的额度
            #  自动初始化（推荐）

            return AccountInfoResponse(
                level=UserLevel.FREE.value,
                level_name=UserLevel.get_descriptions()[UserLevel.FREE],
                monthly_balance=settings.USER_DAILY_TOKEN_LIMIT,
                remaining_balance=free_limit_remaining,
                total_consumed=user_already_used_weighted,
                total_amount=settings.USER_DAILY_TOKEN_LIMIT
            )

        # ==================== 2. 获取会员配置 ====================

        membership = await MembershipDAO.get_by_code(db, account.level_code)

        # ==================== 3. 计算总剩余余额 ====================

        total_balance = account.monthly_balance + account.permanent_balance


        # ==================== 5. 返回 ====================
        return AccountInfoResponse(
            level=account.level_code if account else TokenConsumeSource.FREE.value,
            level_name=membership.level_name if membership else "免费用户",
            expire_at=account.expire_at if account else None,
            monthly_balance=account.monthly_balance + settings.USER_DAILY_TOKEN_LIMIT,
            permanent_balance=account.permanent_balance,
            remaining_balance=total_balance + user_already_used_weighted,
            total_consumed=account.total_consumed + user_already_used_weighted,
            total_amount = account.total_amount + settings.USER_DAILY_TOKEN_LIMIT
        )

    @staticmethod
    async def grant_order_benefits(db, order):
        """
        发放订单权益（核心闭环）

        支持：
        - 会员发放
        - Token充值
        - 流水记录
        - 幂等控制
        - 事务保证
        """

        logger.info(f"[权益] 开始发放 order_no={order.order_no}")

        # ==================== 1. 获取用户账户 ====================

        account = await db.get(UserAccount, order.user_id)

        if not account:
            #  自动初始化
            logger.error(f"[权益] 用户账户不存在 uid={order.user_id}")
            account = await AccountService.init_account(db, order.user_id)

        # ==================== 2. 根据订单类型分发 ====================

        if order.order_type == "MEMBERSHIP":
            await AccountService._grant_membership(db, account, order)

        elif order.order_type == "TOKEN_PACKAGE":
            await AccountService._grant_token_package(db, account, order)

        else:
            logger.error(f"[权益] 未知订单类型: {order.order_type}")
            raise ServiceWarning("未知订单类型")

        logger.info(f"[DEBUG] before: m={account.monthly_balance}, p={account.permanent_balance}")
        logger.info(f"[DEBUG] after: m={account.monthly_balance}, p={account.permanent_balance}")
        logger.info(f"[权益] 发放完成 order_no={order.order_no}")

    @staticmethod
    async def _grant_membership(db: AsyncSession, account: UserAccount, order):
        """
        会员发放 + 月度Token + 流水
        """

        membership = await MembershipDAO.get_by_code(db, order.target_code)
        if not membership:
            raise Exception("会员不存在")

        now = datetime.utcnow()
        duration = timedelta(days=membership.duration_days)

        # ==================== 1. 计算过期时间 ====================
        if account.expire_at:
            expire_at = AccountService._as_utc_naive(account.expire_at)
        else:
            expire_at = None

        if expire_at and expire_at > now:
            benefit_start = expire_at
        else:
            benefit_start = now

        new_expire = benefit_start + duration

        account.level_code = membership.level_code
        account.expire_at = new_expire

        logger.info(f"[会员] level={membership.level_code}, expire={new_expire}")

        # ==================== 2. 创建并执行月度Token分期计划 ====================

        if membership.monthly_token_allowance > 0:
            # 幂等保护：同一个订单只允许生成一组发放计划，支付回调重试不会重复加额度。
            if await MembershipTokenGrantPlanDAO.exists_by_order_no(db, order.order_no):
                logger.info(f"[会员] 发放计划已存在 order_no={order.order_no}")
                return

            plans = AccountService._build_membership_token_plans(
                user_id=account.user_id,
                order_no=order.order_no,
                level_code=membership.level_code,
                monthly_token_allowance=membership.monthly_token_allowance,
                duration_days=membership.duration_days,
                start_at=now,
                expire_at=new_expire,
            )

            MembershipTokenGrantPlanDAO.add_all(db, plans)

            immediate_plans = [
                plan for plan in plans
                if plan.scheduled_at <= now and plan.plan_type == "GRANT"
            ]

            # 订单支付成功时立即执行当前到期的首发计划，让用户马上拿到 60% 月度额度。
            for plan in immediate_plans:
                await AccountService.issue_membership_token_plan(db, account, plan, now)

            logger.info(
                f"[会员] 月度Token首发 +{sum(plan.amount for plan in immediate_plans)}, "
                f"plans={len(plans)}"
            )

    @staticmethod
    async def _grant_token_package(db: AsyncSession, account: UserAccount, order):
        """
        Token充值 + 流水
        """

        package = await PackageDAO.get_by_code(db, order.target_code)
        if not package:
            raise Exception("Token包不存在")

        token_amount = package.token_amount

        # ==================== 1. 增加余额 ====================

        account.permanent_balance += token_amount
        account.total_amount += token_amount

        logger.info(f"[Token] permanent +{token_amount}")

        # ==================== 2. 写流水 ====================

        log = AccountLog(
            user_id=account.user_id,
            biz_id=order.order_no,
            biz_type=BizType.ORDER.value,
            change_type=ChargeType.RECHARGE.value,
            asset_type=AssetType.PERMANENT.value,
            amount=token_amount,
            balance_after=account.permanent_balance,
            extra={
                "package_code": package.package_code,
                "package_name": package.package_name
            }
        )

        db.add(log)

    @staticmethod
    async def init_account(db: AsyncSession, user_id: int) -> UserAccount:
        """
        初始化用户账户（幂等）

         场景：
        - 用户第一次进入系统
        - 用户第一次下单
        - 用户第一次使用AI

         特点：
        ✔ 幂等（多次调用不会重复创建）
        ✔ 默认创建 basic 账户
        ✔ 可扩展（注册送Token等）
        """

        # ==================== 1. 查询是否已存在 ====================
        account = await UserAccountDAO.get_active_account(db=db, user_id=user_id)
        if account:
            logger.info(f"[账户] 已存在 uid={user_id}")
        else:
            # ==================== 2. 创建账户 ====================

            account = UserAccount(
                user_id=user_id,
                level_code=UserLevel.FREE.value,  # 默认免费会员
                expire_at=None,
                monthly_balance=0,
                permanent_balance=0,
                total_consumed=0,
                total_amount=0,
                last_reset_at=None,
                version=0,
                updated_at=datetime.utcnow()
            )

            db.add(account)
            logger.info(f"[账户权益] 创建成功 user_id={user_id}")

        return account
