from datetime import datetime, timedelta, timezone

from dateutil.relativedelta import relativedelta
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from common.config.config import settings
from common.exception.lzsd_exception import ServiceWarning
from core.entity.do.membership_token_grant_plan_do import MembershipTokenGrantPlan
from core.entity.do.user_account_do import UserAccount, AccountLog
from core.entity.vo.user_vo import AccountInfoResponse, AssetUsageItem, BonusGrantItem, BonusGrantListResponse, UsageOverview
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
    def _next_friday(value: datetime) -> datetime:
        days_until_friday = (4 - value.weekday()) % 7
        if days_until_friday == 0:
            days_until_friday = 7

        return (value + timedelta(days=days_until_friday)).replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def _split_bonus_token_allowance(total_amount: int) -> list[int]:
        # 补给策略：付费额度先 100% 到账；后续四个周五各额外发 10%。
        bonus_amounts = [
            total_amount * 10 // 100,
            total_amount * 10 // 100,
            total_amount * 10 // 100,
            total_amount * 10 // 100,
        ]
        return bonus_amounts

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
        bonus_amounts = AccountService._split_bonus_token_allowance(monthly_token_allowance)

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

            # period_no=0 是付费基础额度，支付成功立即到账，计入 monthly_balance/total_amount。
            plans.append(
                MembershipTokenGrantPlan(
                    user_id=user_id,
                    order_no=order_no,
                    level_code=level_code,
                    cycle_no=cycle_no,
                    period_no=0,
                    plan_type="BASE",
                    amount=monthly_token_allowance,
                    scheduled_at=cycle_start,
                    membership_expire_at=expire_at,
                    status="PENDING",
                    extra={"source": "membership", "grant_kind": "base"},
                )
            )

            first_bonus_at = AccountService._next_friday(cycle_start)
            for index, amount in enumerate(bonus_amounts, start=1):
                # period_no=1-4 是周五补给奖励，计入 bonus_balance，不计入 total_amount。
                plans.append(
                    MembershipTokenGrantPlan(
                        user_id=user_id,
                        order_no=order_no,
                        level_code=level_code,
                        cycle_no=cycle_no,
                        period_no=index,
                        plan_type="BONUS",
                        amount=amount,
                        scheduled_at=first_bonus_at + timedelta(days=(index - 1) * 7),
                        membership_expire_at=expire_at,
                        status="PENDING",
                        extra={"source": "membership", "grant_kind": "bonus", "grant_mode": "friday_bonus"},
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
            asset_type: AssetType = AssetType.MONTHLY,
            balance_after: int | None = None,
            extra: dict | None = None,
    ) -> None:
        log = AccountLog(
            user_id=account.user_id,
            biz_id=biz_id,
            biz_type=BizType.ORDER.value,
            change_type=ChargeType.RECHARGE.value,
            asset_type=asset_type.value,
            amount=amount,
            balance_after=account.monthly_balance if balance_after is None else balance_after,
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
            asset_type: AssetType = AssetType.MONTHLY,
            balance_after: int | None = None,
    ) -> None:
        if amount <= 0:
            return

        log = AccountLog(
            user_id=account.user_id,
            biz_id=biz_id,
            biz_type=BizType.SYSTEM.value,
            change_type=ChargeType.EXPIRE.value,
            asset_type=asset_type.value,
            amount=-amount,
            balance_after=account.monthly_balance if balance_after is None else balance_after,
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
            # 年会员新月周期：清掉旧月度余额和补给奖励，再由后续 BASE/BONUS 计划补入新月额度。
            old_monthly = account.monthly_balance or 0
            old_monthly_total = account.monthly_total_amount or 0
            old_bonus = account.bonus_balance or 0
            account.monthly_balance = 0
            account.monthly_total_amount = 0
            account.bonus_balance = 0
            account.bonus_total_amount = 0
            account.total_amount = max((account.total_amount or 0) - old_monthly_total, 0)
            account.last_reset_at = now

            AccountService._write_monthly_reset_log(
                db=db,
                account=account,
                biz_id=f"{plan.order_no}:cycle:{plan.cycle_no}:reset",
                amount=old_monthly,
                level_code=plan.level_code,
                reason="monthly_cycle_reset",
            )
            AccountService._write_monthly_reset_log(
                db=db,
                account=account,
                biz_id=f"{plan.order_no}:cycle:{plan.cycle_no}:bonus-reset",
                amount=old_bonus,
                level_code=plan.level_code,
                reason="monthly_bonus_reset",
                asset_type=AssetType.BONUS,
                balance_after=account.bonus_balance,
            )
        elif plan.plan_type == "BASE":
            # 付费基础额度：用户买多少先到账多少，进入 monthly_balance 和 total_amount。
            account.monthly_balance += plan.amount
            account.monthly_total_amount += plan.amount
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
                    "grant_kind": "base",
                },
            )
        else:
            # 补给奖励：独立进入 bonus_balance/bonus_total_amount，不污染付费 total_amount。
            account.bonus_balance += plan.amount
            account.bonus_total_amount += plan.amount

            AccountService._write_monthly_recharge_log(
                db=db,
                account=account,
                biz_id=f"{plan.order_no}:cycle:{plan.cycle_no}:bonus:{plan.period_no}",
                amount=plan.amount,
                level_code=plan.level_code,
                asset_type=AssetType.BONUS,
                balance_after=account.bonus_balance,
                extra={
                    "cycle_no": plan.cycle_no,
                    "period_no": plan.period_no,
                    "grant_kind": "bonus",
                    "grant_mode": "friday_bonus",
                },
            )

        plan.status = "ISSUED"
        plan.issued_at = now

    @staticmethod
    async def claim_due_bonus_plans(
            db: AsyncSession,
            user_id: int,
            now: datetime | None = None,
    ) -> int:
        """
        用户登录/上线时领取已到周五的补给奖励。
        """
        now = now or datetime.utcnow()
        account = await UserAccountDAO.get_active_account(db=db, user_id=user_id)
        if not account:
            return 0

        plans = await MembershipTokenGrantPlanDAO.get_due_bonus_plans(db, user_id, now)
        total_claimed = 0

        for plan in plans:
            # 每周补给只保留 1 天领取窗口；错过后不补发，避免跨周累计领取。
            if now >= plan.scheduled_at + timedelta(days=1):
                plan.status = "CANCELED"

                plan.issued_at = now
                plan.extra = {
                    **(plan.extra or {}),
                    "cancel_reason": "bonus_window_missed",
                }
                logger.info(
                    f"[会员补给] 用户错过领取窗口 user_id={user_id}, "
                    f"plan_id={plan.id}, scheduled_at={plan.scheduled_at}"
                )
                continue

            await AccountService.issue_membership_token_plan(db, account, plan, now)
            if plan.status == "ISSUED":
                total_claimed += plan.amount

        if total_claimed > 0:
            logger.info(f"[会员补给] 用户上线领取 user_id={user_id}, bonus=+{total_claimed}")

        return total_claimed

    @staticmethod
    def _format_bonus_plan_status(plan: MembershipTokenGrantPlan, now: datetime) -> str:
        if plan.status == "ISSUED":
            return "received"
        if plan.status == "CANCELED":
            return "missed"
        if now >= plan.scheduled_at + timedelta(days=1):
            return "missed"
        if plan.scheduled_at <= now:
            return "available"
        return "pending"

    @staticmethod
    async def get_current_bonus_list(db: AsyncSession, user_id: int) -> BonusGrantListResponse:
        now = datetime.utcnow()

        await AccountService.claim_due_bonus_plans(db, user_id, now)
        account = await UserAccountDAO.get_active_account(db=db, user_id=user_id)
        plans = await MembershipTokenGrantPlanDAO.get_current_bonus_plans(db, user_id, now)
        items = [
            BonusGrantItem(
                id=plan.id,
                orderNo=plan.order_no,
                cycleNo=plan.cycle_no,
                periodNo=plan.period_no,
                amount=plan.amount,
                date=plan.scheduled_at.strftime("%m.%d"),
                scheduledAt=plan.scheduled_at.strftime("%Y-%m-%d %H:%M:%S"),
                issuedAt=plan.issued_at.strftime("%Y-%m-%d %H:%M:%S") if plan.issued_at else None,
                status=AccountService._format_bonus_plan_status(plan, now),
                rawStatus=plan.status,
            )
            for plan in plans
        ]

        return BonusGrantListResponse(
            availableAmount=account.bonus_total_amount if account else 0,
            weeklyAmount=items[0].amount if items else 0,
            list=items,
        )

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
    def _build_asset_usage_item(key: str, name: str, total: int, available: int) -> AssetUsageItem:
        # total 记录本周期/累计发放总量，available 是当前余额；已消耗由两者差值推导。
        total = max(total or 0, 0)
        available = max(available or 0, 0)
        used = max(total - available, 0)
        used_percent = AccountService._calc_used_percent(used, total)

        return AssetUsageItem(
            key=key,
            name=name,
            total=total,
            available=available,
            used=used,
            usedPercent=used_percent,
        )

    @staticmethod
    def _calc_used_percent(used: int, total: int) -> int:
        # 有消耗但不足 1% 时返回 1，避免前端看起来像完全没用过。
        if used <= 0 or total <= 0:
            return 0

        return max(1, int(used * 100 / total))

    @staticmethod
    def _build_usage_overview(
            account: UserAccount | None,
            free_total: int,
            free_available: int,
    ) -> UsageOverview:
        monthly_total = account.monthly_total_amount if account else 0
        monthly_available = account.monthly_balance if account else 0
        permanent_total = account.permanent_total_amount if account else 0
        permanent_available = account.permanent_balance if account else 0
        bonus_total = account.bonus_total_amount if account else 0
        bonus_available = account.bonus_balance if account else 0

        items = [
            AccountService._build_asset_usage_item("monthly", "付费额度", monthly_total, monthly_available),
            AccountService._build_asset_usage_item("permanent", "永久额度", permanent_total, permanent_available),
            AccountService._build_asset_usage_item("bonus", "补给奖励", bonus_total, bonus_available),
            AccountService._build_asset_usage_item("free", "基础免费", free_total, free_available),
        ]

        total_amount = sum(item.total for item in items)
        available_amount = sum(item.available for item in items)
        used_amount = sum(item.used for item in items)
        used_percent = AccountService._calc_used_percent(used_amount, total_amount)
        return UsageOverview(
            availableAmount=available_amount,
            totalAmount=total_amount,
            usedAmount=used_amount,
            usedPercent=used_percent,
            status="normal",
            totalItems=items,
        )

    @staticmethod
    async def get_account_info(db: AsyncSession, user_id: int):
        """
        获取用户资产信息
        """
        await AccountService.claim_due_bonus_plans(db, user_id)

        # =============计算个人每天免费额度===================
        usage_service = UsageService(db)
        free_used = await usage_service.get_user_monthly_free_used(user_id)
        # 计算今天剩余可用的免费额度
        free_limit_remaining = max(0, settings.USER_MONTHLY_FREE_TOKEN_LIMIT - free_used)
        usage_overview = AccountService._build_usage_overview(
            account=None,
            free_total=settings.USER_MONTHLY_FREE_TOKEN_LIMIT,
            free_available=free_limit_remaining,
        )
        # ==================== 1. 获取账户 ====================
        account = await UserAccountDAO.get_active_account(db=db, user_id=user_id)
        if not account:
            # 每日的额度
            #  自动初始化（推荐）

            return AccountInfoResponse(
                level=UserLevel.FREE.value,
                level_name=UserLevel.get_descriptions()[UserLevel.FREE],
                permanent_balance=0,
                **usage_overview.model_dump(),
            )

        # ==================== 2. 获取会员配置 ====================

        membership = await MembershipDAO.get_by_code(db, account.level_code)

        # ==================== 3. 计算总剩余余额 ====================

        usage_overview = AccountService._build_usage_overview(
            account=account,
            free_total=settings.USER_MONTHLY_FREE_TOKEN_LIMIT,
            free_available=free_limit_remaining,
        )


        # ==================== 5. 返回 ====================
        return AccountInfoResponse(
            level=account.level_code if account else TokenConsumeSource.FREE.value,
            level_name=membership.level_name if membership else "免费用户",
            expire_at=account.expire_at if account else None,
            permanent_balance=account.permanent_balance,
            **usage_overview.model_dump(),
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
                if plan.scheduled_at <= now and plan.plan_type == "BASE"
            ]

            # 订单支付成功时立即执行基础额度计划，让用户买到的额度 100% 先到账。
            for plan in immediate_plans:
                await AccountService.issue_membership_token_plan(db, account, plan, now)

            logger.info(
                f"[会员] 月度Token基础额度 +{sum(plan.amount for plan in immediate_plans)}, "
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
        account.permanent_total_amount += token_amount
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
                monthly_total_amount=0,
                permanent_balance=0,
                permanent_total_amount=0,
                bonus_balance=0,
                total_consumed=0,
                total_amount=0,
                bonus_total_amount=0,
                last_reset_at=None,
                version=0,
                updated_at=datetime.utcnow()
            )

            db.add(account)
            logger.info(f"[账户权益] 创建成功 user_id={user_id}")

        return account
