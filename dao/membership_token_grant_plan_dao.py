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
            .with_for_update()  # 去掉 skip_locked
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_due_system_plans(
            db: AsyncSession,
            now: datetime,
            limit: int = 200
    ) -> list[MembershipTokenGrantPlan]:
        stmt = (
            select(MembershipTokenGrantPlan)
            .where(
                MembershipTokenGrantPlan.status == "PENDING",
                MembershipTokenGrantPlan.scheduled_at <= now,
                MembershipTokenGrantPlan.plan_type.in_(["BASE", "RESET"]),
            )
            .order_by(
                MembershipTokenGrantPlan.scheduled_at.asc(),
                MembershipTokenGrantPlan.cycle_no.asc(),
                MembershipTokenGrantPlan.period_no.asc(),
                MembershipTokenGrantPlan.id.asc(),
            )
            .with_for_update()
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_due_bonus_plans(
            db: AsyncSession,
            user_id: int,
            now: datetime,
            limit: int = 20
    ) -> list[MembershipTokenGrantPlan]:
        stmt = (
            select(MembershipTokenGrantPlan)
            .where(
                MembershipTokenGrantPlan.user_id == user_id,
                MembershipTokenGrantPlan.status == "PENDING",
                MembershipTokenGrantPlan.plan_type == "BONUS",
                MembershipTokenGrantPlan.scheduled_at <= now,
            )
            .order_by(
                MembershipTokenGrantPlan.scheduled_at.asc(),
                MembershipTokenGrantPlan.cycle_no.asc(),
                MembershipTokenGrantPlan.period_no.asc(),
                MembershipTokenGrantPlan.id.asc(),
            )
            .with_for_update()
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_current_bonus_plans(
            db: AsyncSession,
            user_id: int,
            now: datetime,
    ) -> list[MembershipTokenGrantPlan]:
        current_cycle = (
            select(
                MembershipTokenGrantPlan.order_no,
                MembershipTokenGrantPlan.cycle_no,
            )
            .where(
                MembershipTokenGrantPlan.user_id == user_id,
                MembershipTokenGrantPlan.plan_type == "BONUS",
                MembershipTokenGrantPlan.scheduled_at <= now,
                MembershipTokenGrantPlan.membership_expire_at > now,
            )
            .order_by(MembershipTokenGrantPlan.scheduled_at.desc())
            .limit(1)
            .subquery()
        )

        stmt = (
            select(MembershipTokenGrantPlan)
            .join(
                current_cycle,
                (MembershipTokenGrantPlan.order_no == current_cycle.c.order_no)
                & (MembershipTokenGrantPlan.cycle_no == current_cycle.c.cycle_no)
            )
            .where(
                MembershipTokenGrantPlan.user_id == user_id,
                MembershipTokenGrantPlan.plan_type == "BONUS",
            )
            .order_by(MembershipTokenGrantPlan.period_no.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
