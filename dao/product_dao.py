from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.entity.do.membership_levels_do import MembershipLevel
from core.entity.do.package_plans_do import PackagePlan


class ProductDAO:
    """
    产品DAO层

    职责：
    - 只负责查数据库
    - 不做业务逻辑
    """

    @staticmethod
    async def get_memberships(db: AsyncSession):
        """
        查询在售会员（按等级排序）

        :param db: 数据库会话
        :return: MembershipLevel 列表
        """
        stmt = (
            select(MembershipLevel)
            .where(MembershipLevel.status == 1)
            .order_by(MembershipLevel.rank_weight.asc())
        )

        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_token_packages(db: AsyncSession):
        """
        查询在售Token包（按排序字段）

        :param db: 数据库会话
        :return: PackagePlan 列表
        """
        stmt = (
            select(PackagePlan)
            .where(PackagePlan.status == 1)
            .order_by(PackagePlan.sort_order.asc())
        )

        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_membership_by_code(db: AsyncSession, level_code: str):
        """
        根据 level_code 查询会员配置

        :param db: 数据库会话
        :param level_code: 会员编码（如 pro_monthly）
        :return: MembershipLevel | None
        """
        stmt = (
            select(MembershipLevel)
            .where(MembershipLevel.level_code == level_code)
            .limit(1)
        )

        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_package_by_code(db: AsyncSession, package_code: str):
        """
        根据 package_code 查询Token充值包

        :param db: 数据库会话
        :param package_code: 包编码（如 token_small）
        :return: PackagePlan | None
        """
        stmt = (
            select(PackagePlan)
            .where(PackagePlan.package_code == package_code)
            .limit(1)
        )

        result = await db.execute(stmt)
        return result.scalars().first()