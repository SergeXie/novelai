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
        aimodel_dao = AiModelDAO(db)
        return await aimodel_dao.list_models(
            only_enabled=only_enabled,
        )