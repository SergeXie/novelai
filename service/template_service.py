from sqlalchemy.ext.asyncio import AsyncSession
from dao.template_dao import TemplateDAO


class TemplateService:

    @staticmethod
    async def list_templates(db: AsyncSession):
        """
        获取模板列表
        """
        return await TemplateDAO.list_templates(db)