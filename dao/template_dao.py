from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.entity.do.mc_template import McTemplate


class TemplateDAO:

    @staticmethod
    async def list_templates(
        db: AsyncSession,
    ) -> list[McTemplate]:
        """
        获取启用的模板列表
        """
        stmt = (
            select(McTemplate)
            .where(McTemplate.status == 1)
            .order_by(McTemplate.id.asc())
        )

        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_template_by_template_id(
            db: AsyncSession,
            template_id: str,
    ) -> McTemplate | None:
        stmt = select(McTemplate).where(
            McTemplate.template_id == template_id,
            McTemplate.status == 1
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()