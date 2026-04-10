from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.entity.do.token_usage_log_do import TokenUsageLog
from core.entity.do.user_account_do import AccountLog
from core.entity.do.users_do import User


class UserDAO:

    @staticmethod
    async def get_by_account(
        db: AsyncSession,
        account: str
    ) -> User | None:

        stmt = select(User).where(User.account == account)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_uuid(
        db: AsyncSession,
        user_uuid: str
    ) -> User | None:
        stmt = select(User).where(User.uuid == user_uuid)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


    @staticmethod
    async def create(
        db: AsyncSession,
        user: User
    ) -> None:
        try:

            db.add(user)
            await db.flush()  # 生成 pkId

        except Exception as e:
            await db.rollback()
            raise e

    @staticmethod
    async def update_password(
        db: AsyncSession,
        user_id: int,
        new_password: str
    ):

        stmt = (
            update(User)
            .where(User.pkId == user_id)
            .values(password=new_password)
        )

        await db.execute(stmt)
        await db.commit()

    @staticmethod
    async def create_log(
            db,
            user_id:int,
            request_id:str,
            monthly_amount,
            permanent_amount:int,
            total_amount:int,
            balance_snapshot:dict,
    ):
        """
        写账户流水
        """

        # ==================== 写 usage_logs ====================
        usage_log = TokenUsageLog(
            user_id=user_id,
            request_id=request_id,
            action_type="CONSUME",
            monthly_amount=monthly_amount,
            permanent_amount=permanent_amount,
            total_amount=total_amount,
            balance_snapshot=balance_snapshot
        )

        db.add(usage_log)