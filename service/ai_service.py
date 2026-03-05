from sqlalchemy.ext.asyncio import AsyncSession

from dao.ai_log_dao import AILogDAO
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

    async def delete_history(self, db, uid: int, request_ids: list):
        await AILogDAO.logic_delete(
            db=db,
            uid=uid,
            request_ids=request_ids
        )

        return True