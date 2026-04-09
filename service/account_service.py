from datetime import datetime, timedelta, timezone

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.exception.lzsd_exception import ServiceWarning
from core.entity.do.user_account_do import UserAccount, AccountLog
from core.entity.vo.user_vo import AccountInfoResponse
from core.enums.constants import UserLevel, BizType, ChargeType, AssetType
from dao.membership_dao import MembershipDAO
from dao.package_dao import PackageDAO
from dao.user_account_dao import UserAccountDAO


class AccountService:
    """
    账户服务（发权益）
    """

    @staticmethod
    async def get_account_info(db: AsyncSession, user_id: int):
        """
        获取用户资产信息
        """
        # ==================== 1. 获取账户 ====================
        account = await UserAccountDAO.get_active_account(db=db, user_id=user_id)
        if not account:
            # 每日的额度
            #  自动初始化（推荐）

            return AccountInfoResponse(
                level=UserLevel.FREE.value,
                level_name=UserLevel.get_descriptions()[UserLevel.FREE],
            )

        # ==================== 2. 获取会员配置 ====================

        membership = await MembershipDAO.get_by_code(db, account.level_code)

        # ==================== 3. 计算总剩余余额 ====================

        total_balance = account.monthly_balance + account.permanent_balance

        # ==================== 4. 处理权益 ====================

        unlocked_models = []
        extra_privileges = {}

        if membership:
            unlocked_models = membership.unlocked_models or []
            extra_privileges = membership.extra_privileges or {}

        # ==================== 5. 返回 ====================
        # 每日的额度 + 总月度赠送额度 + 永久有效额度
        user_daily_token_limit = account.monthly_balance + account.permanent_balance

        return AccountInfoResponse(
            level=account.level_code if account else "free",
            level_name=membership.level_name if membership else "免费用户",
            expire_at=account.expire_at if account else None,
            monthly_balance=account.monthly_balance,
            permanent_balance=account.permanent_balance,
            remaining_balance=total_balance,
            unlocked_models=unlocked_models,
            extra_privileges=extra_privileges,
            total_consumed=account.total_consumed,
            total_amount = account.total_amount
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

        now = datetime.now(timezone.utc)
        duration = timedelta(days=membership.duration_days)

        # ==================== 1. 计算过期时间 ====================
        if account.expire_at:
            expire_at = account.expire_at

            # 如果是 naive → 强制变成 UTC aware
            if expire_at.tzinfo is None:
                expire_at = expire_at.replace(tzinfo=timezone.utc)
        else:
            expire_at = None

        if expire_at and expire_at > now:
            new_expire = expire_at + duration
        else:
            new_expire = now + duration

        account.level_code = membership.level_code
        account.expire_at = new_expire

        logger.info(f"[会员] level={membership.level_code}, expire={new_expire}")

        # ==================== 2. 发放月度Token ====================

        if membership.monthly_token_allowance > 0:
            account.monthly_balance += membership.monthly_token_allowance
            account.total_amount += membership.monthly_token_allowance
            # 写流水（MONTHLY）
            log = AccountLog(
                user_id=account.user_id,
                biz_id=order.order_no,
                biz_type=BizType.ORDER.value,
                change_type=ChargeType.RECHARGE.value,
                asset_type=AssetType.MONTHLY.value,
                amount=membership.monthly_token_allowance,
                balance_after=account.monthly_balance,
                extra={
                    "source": "membership",
                    "level": membership.level_code
                }
            )

            db.add(log)

            logger.info(f"[DEBUG] before: m={account.monthly_balance}, p={account.permanent_balance}")
            logger.info(f"[DEBUG] after: m={account.monthly_balance}, p={account.permanent_balance}")
            logger.info(f"[会员] 月度Token +{membership.monthly_token_allowance}")

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
                last_reset_at=None,
                version=0,
                updated_at=datetime.utcnow()
            )

            db.add(account)
            logger.info(f"[账户权益] 创建成功 user_id={user_id}")

        return account