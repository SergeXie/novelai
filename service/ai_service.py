from sqlalchemy.ext.asyncio import AsyncSession
from dao.ai_model_dao import AiModelDAO


class AiModelService:

    @staticmethod
    async def list_models(
        db: AsyncSession,
        *,
        only_enabled: bool = True,
    ):
        """
        获取模型列表
        """
        return await AiModelDAO.list_models(
            db,
            only_enabled=only_enabled,
        )