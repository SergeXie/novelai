from datetime import datetime, timedelta
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
        stmt = (
            select(MembershipTokenGrantPlan)
            .where(
                MembershipTokenGrantPlan.user_id == user_id,
                MembershipTokenGrantPlan.plan_type == "BONUS",
                MembershipTokenGrantPlan.membership_expire_at > now,
            )
            .order_by(
                MembershipTokenGrantPlan.scheduled_at.asc(),
                MembershipTokenGrantPlan.order_no.asc(),
                MembershipTokenGrantPlan.cycle_no.asc(),
                MembershipTokenGrantPlan.period_no.asc(),
            )
        )
        result = await db.execute(stmt)
        plans = list(result.scalars().all())

        if not plans:
            return []

        cycles: dict[tuple[str, int], list[MembershipTokenGrantPlan]] = {}
        for plan in plans:
            cycles.setdefault((plan.order_no, plan.cycle_no), []).append(plan)

        for cycle_plans in cycles.values():
            last_bonus_at = max(plan.scheduled_at for plan in cycle_plans)
            # 展示当前仍在补给窗口内的周期；若首个周五还没到，也会命中第一组未来周期。
            if now <= last_bonus_at + timedelta(days=1):
                return sorted(cycle_plans, key=lambda plan: plan.period_no)

        return sorted(list(cycles.values())[-1], key=lambda plan: plan.period_no)
