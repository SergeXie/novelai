from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.entity.do.user_account_do import UserAccount


class UserAccountDAO:

    @staticmethod
    async def get_active_account(db:AsyncSession, user_id:int)->UserAccount | None:
        result = await db.execute(select(UserAccount).where(UserAccount.user_id == user_id))
        account = result.scalars().first()

        if account and not account.is_expired:
            return account
        return None

