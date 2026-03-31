from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.exception.lzsd_exception import ServiceWarning
from core.entity.do.token_usage_log_do import TokenUsageLog
from core.entity.do.user_account_do import UserAccount, AccountLog
from dao.membership_dao import MembershipDAO
from dao.package_dao import PackageDAO


class AccountService:
    """
    账户服务（发权益）
    """

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

        account = await db.get(UserAccount, order.uid)

        if not account:
            logger.error(f"[权益] 用户账户不存在 uid={order.uid}")
            raise ServiceWarning("用户账户不存在")

        # ==================== 2. 根据订单类型分发 ====================

        if order.order_type == "MEMBERSHIP":
            await AccountService._grant_membership(db, account, order)

        elif order.order_type == "TOKEN_PACKAGE":
            await AccountService._grant_token_package(db, account, order)

        else:
            logger.error(f"[权益] 未知订单类型: {order.order_type}")
            raise ServiceWarning("未知订单类型")

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

        if account.expire_at and account.expire_at > now:
            new_expire = account.expire_at + duration
        else:
            new_expire = now + duration

        account.level_code = membership.level_code
        account.expire_at = new_expire

        logger.info(f"[会员] level={membership.level_code}, expire={new_expire}")

        # ==================== 2. 发放月度Token ====================

        if membership.monthly_token_allowance > 0:
            account.monthly_balance += membership.monthly_token_allowance

            # 写流水（MONTHLY）
            log = AccountLog(
                uid=account.uid,
                biz_id=order.order_no,
                biz_type="ORDER",
                change_type="RECHARGE",
                asset_type="MONTHLY",
                amount=membership.monthly_token_allowance,
                balance_after=account.monthly_balance,
                extra={
                    "source": "membership",
                    "level": membership.level_code
                }
            )

            db.add(log)

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

        logger.info(f"[Token] permanent +{token_amount}")

        # ==================== 2. 写流水 ====================

        log = AccountLog(
            uid=account.uid,
            biz_id=order.order_no,
            biz_type="ORDER",
            change_type="RECHARGE",
            asset_type="PERMANENT",
            amount=token_amount,
            balance_after=account.permanent_balance,
            extra={
                "package_code": package.package_code,
                "package_name": package.package_name
            }
        )

        db.add(log)

    @staticmethod
    async def init_account(db: AsyncSession, uid: str) -> UserAccount:
        """
        初始化用户账户（幂等）

        👉 场景：
        - 用户第一次进入系统
        - 用户第一次下单
        - 用户第一次使用AI

        👉 特点：
        ✔ 幂等（多次调用不会重复创建）
        ✔ 默认创建 basic 账户
        ✔ 可扩展（注册送Token等）
        """

        # ==================== 1. 查询是否已存在 ====================

        stmt = select(UserAccount).where(UserAccount.uid == uid)
        result = await db.execute(stmt)
        account = result.scalars().first()

        if account:
            logger.info(f"[账户] 已存在 uid={uid}")
            return account

        # ==================== 2. 创建账户 ====================

        account = UserAccount(
            uid=uid,
            level_code="basic",  # 默认基础会员
            expire_at=None,

            monthly_balance=0,
            permanent_balance=0,

            total_consumed=0,
            last_reset_at=None,

            version=0,
            updated_at=datetime.utcnow()
        )

        db.add(account)

        logger.info(f"[账户] 创建成功 uid={uid}")

        return account