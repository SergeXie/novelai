from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.entity.do.package_plans_do import PackagePlan


class PackageDAO:
    """
    Token包 DAO
    """

    @staticmethod
    async def get_by_code(db: AsyncSession, package_code: str) -> PackagePlan | None:
        """
        根据 package_code 获取充值包

        :param db:
        :param package_code:
        :return:
        """

        logger.info(f"[DAO] 查询会员 package_code={package_code}")

        stmt = select(PackagePlan).where(
            PackagePlan.package_code == package_code,
            PackagePlan.status == 1
        )

        result = await db.execute(stmt)

        return result.scalars().first()