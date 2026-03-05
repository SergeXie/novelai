from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

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