from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.entity.do.membership_levels_do import MembershipLevel


class MembershipDAO:
    """
    会员配置 DAO
    """

    @staticmethod
    async def get_by_code(db: AsyncSession, level_code: str) -> MembershipLevel | None:
        """
        根据 level_code 获取会员配置

        :param db: 数据库会话
        :param level_code: basic / pro_monthly / pro_annual / enterprise
        :return: MembershipLevel 或 None
        """

        logger.info(f"[DAO] 查询Token level_code={level_code}")

        stmt = select(MembershipLevel).where(
            MembershipLevel.level_code == level_code,
            MembershipLevel.status == 1  # 只查在售的
        )

        result = await db.execute(stmt)

        # scalars().first() 返回 ORM对象
        return result.scalars().first()