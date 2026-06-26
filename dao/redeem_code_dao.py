from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.entity.do.redeem_code_do import RedeemCode


class RedeemCodeDAO:
    @staticmethod
    async def get_by_code_for_update(db: AsyncSession, code: str) -> RedeemCode | None:
        stmt = (
            select(RedeemCode)
            .where(RedeemCode.code == code)
            .with_for_update()
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_active_user_codes_for_update(db: AsyncSession, user_id: int, now) -> list[RedeemCode]:
        stmt = (
            select(RedeemCode)
            .where(
                RedeemCode.user_id == user_id,
                RedeemCode.status == 1,
                RedeemCode.remaining_amount > 0,
                RedeemCode.token_expired_time > now,
            )
            .order_by(RedeemCode.token_expired_time.asc(), RedeemCode.redeem_time.asc())
            .with_for_update()
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_expired_redeemed_codes_for_update(db: AsyncSession, now) -> list[RedeemCode]:
        stmt = (
            select(RedeemCode)
            .where(
                RedeemCode.status == 1,
                RedeemCode.token_expired_time <= now,
            )
            .order_by(RedeemCode.token_expired_time.asc())
            .with_for_update()
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def list_user_redeemed_codes(
            db: AsyncSession,
            user_id: int,
            page: int,
            page_size: int,
    ) -> tuple[list[RedeemCode], int]:
        conditions = [
            RedeemCode.user_id == user_id,
            RedeemCode.status.in_([1, 2]),
            RedeemCode.redeem_time.isnot(None),
        ]

        count_stmt = select(func.count()).select_from(RedeemCode).where(*conditions)
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = (
            select(RedeemCode)
            .where(*conditions)
            .order_by(RedeemCode.redeem_time.desc(), RedeemCode.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all()), total
