from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.entity.do.mc_ai_model import McAiModel


class AiModelDAO:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_models(self, only_enabled: bool = True) -> list[McAiModel]:
        try:
            stmt = select(McAiModel)
            if only_enabled:
                stmt = stmt.where(McAiModel.status == 1)
            stmt = stmt.order_by(McAiModel.level.asc())

            result = await self.db.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            logger.error(f"获取模型列表失败: {e}")
            return []

    async def get_model_by_level(self, level: int) -> McAiModel:
        stmt = select(McAiModel).where(McAiModel.level == level)
        result = await self.db.execute(stmt)
        model = result.scalars().first()

        if not model:
            # 这里可以抛出一个自定义异常，方便全局异常处理器捕获
            logger.warning(f"未找到 Level 为 {level} 的模型配置")
            return None
        return model


