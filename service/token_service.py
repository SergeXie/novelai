from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from common.exception.lzsd_exception import ServiceWarning
from core.entity.do.user_account_do import UserAccount
from dao.user_dao import UserDAO

UNIT = 10000  # 万 → 个


class TokenService:

    @staticmethod
    async def consume_tokens(
        db: AsyncSession,
        user_id: int,
        amount: int,
        request_id: str
    ):
        """
        Token扣费核心逻辑（生产级）

        :param db:
        :param user_id:
        :param amount: 本次消耗
        :param request_id: 请求ID（用于幂等）
        """

        logger.info(f"[扣费] user_id={user_id}, amount={amount}, request_id={request_id}")

        # ==================== 1. 查询账户（加锁） ====================

        stmt = select(UserAccount).where(UserAccount.user_id == user_id).with_for_update()
        result = await db.execute(stmt)

        account: UserAccount = result.scalars().first()

        if not account:
            raise ServiceWarning("账户不存在")

        # ==================== 2. 校验余额 ====================

        monthly_real = account.monthly_balance * UNIT
        permanent_real = account.permanent_balance * UNIT

        total_real = monthly_real + permanent_real

        if total_real < amount:
            raise ServiceWarning("Token余额不足")

        # ==================== 扣费 ====================

        consume_monthly = min(monthly_real, amount)
        consume_permanent = amount - consume_monthly

        monthly_real -= consume_monthly
        permanent_real -= consume_permanent

        # ==================== 写回（转回“万”） ====================

        account.monthly_balance = monthly_real // UNIT
        account.permanent_balance = permanent_real // UNIT

        account.total_consumed += amount

        # ==================== 5. 写流水 ====================
        await UserDAO.create_log(
            db=db,
            user_id=user_id,
            request_id=request_id,
            monthly_amount=consume_monthly,
            permanent_amount=consume_permanent,
            total_amount=amount,
            balance_snapshot={
                "monthly": account.monthly_balance,
                "permanent": account.permanent_balance
            }
        )

        logger.info(
            f"[扣费] 成功 uid={user_id}, monthly={consume_monthly}, permanent={consume_permanent}"
        )

        return True