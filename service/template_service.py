from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.entity.do.mc_template import McTemplate
from dao.template_dao import TemplateDAO


class TemplateService:

    @staticmethod
    async def list_templates(db: AsyncSession):
        """
        获取模板列表
        """
        return await TemplateDAO.list_templates(db)

    @staticmethod
    async def get_template_by_key(db: AsyncSession, key: str):
        stmt = select(McTemplate).where(
            McTemplate.template_id == key,
            McTemplate.status == 1
        )
        result = await db.execute(stmt)

        data = result.scalar_one_or_none()
