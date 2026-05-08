from datetime import datetime
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.entity.do.membership_token_grant_plan_do import MembershipTokenGrantPlan


class MembershipTokenGrantPlanDAO:
    @staticmethod
    async def exists_by_order_no(db: AsyncSession, order_no: str) -> bool:
        stmt = (
            select(MembershipTokenGrantPlan.id)
            .where(MembershipTokenGrantPlan.order_no == order_no)
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None

    @staticmethod
    def add_all(db: AsyncSession, plans: Sequence[MembershipTokenGrantPlan]) -> None:
        db.add_all(list(plans))

    @staticmethod
    async def get_due_plans(
            db: AsyncSession,
            now: datetime,
            limit: int = 200
    ) -> list[MembershipTokenGrantPlan]:
        stmt = (
            select(MembershipTokenGrantPlan)
            .where(
                MembershipTokenGrantPlan.status == "PENDING",
                MembershipTokenGrantPlan.scheduled_at <= now,
            )
            .order_by(
                MembershipTokenGrantPlan.scheduled_at.asc(),
                MembershipTokenGrantPlan.cycle_no.asc(),
                MembershipTokenGrantPlan.period_no.asc(),
                MembershipTokenGrantPlan.id.asc(),
            )
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
