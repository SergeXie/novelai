from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.entity.do.user_account_do import UserAccount


class UserAccountDAO:

    @staticmethod
    async def get_expired_memberships(db:AsyncSession):
        from datetime import datetime
        from sqlalchemy import select
        from core.entity.do.user_account_do import UserAccount

        result = await db.execute(
            select(UserAccount).where(
                UserAccount.expire_at < datetime.utcnow(),
                UserAccount.level_code != "free"
            )
        )

        return result.scalars().all()

    @staticmethod
    async def get_active_account(db:AsyncSession, user_id:int)->UserAccount | None:
        result = await db.execute(select(UserAccount).where(UserAccount.user_id == user_id))
        account = result.scalars().first()

        if account:
            return account

        return None


