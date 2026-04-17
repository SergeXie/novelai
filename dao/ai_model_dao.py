import time
from typing import List, Dict

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.entity.do.ai_model import McAiModel


class AiModelDAO:
    _cache_models: List[McAiModel] = None
    _cache_level_map: Dict[int, McAiModel] = {}
    _cache_identifier_map: Dict[str, McAiModel] = {}
    _last_update: float = 0
    CACHE_TTL = 1800  # 10分钟过期

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_models(self, only_enabled: bool = True) -> list[McAiModel]:
        now = time.time()

        # 注意：这里使用 AiModelDAO._xxx 而不是 self._xxx 来判断
        if AiModelDAO._cache_models is None or (now - AiModelDAO._last_update) > AiModelDAO.CACHE_TTL:
            try:
                stmt = select(McAiModel).order_by(McAiModel.weight.desc())
                result = await self.db.execute(stmt)
                all_models = list(result.scalars().all())

                # ！！！核心修改：通过类名赋值，确保所有实例共享
                AiModelDAO._cache_models = all_models
                AiModelDAO._cache_level_map = {m.level: m for m in all_models}
                AiModelDAO._cache_identifier_map = {m.model_identifier: m for m in all_models}
                AiModelDAO._last_update = now

                logger.info(f"AI模型内存索引已重建 (Count: {len(all_models)})")
            except Exception as e:
                logger.error(f"刷新模型缓存失败: {e}")
                return []

        if only_enabled:
            return [m for m in AiModelDAO._cache_models if m.status == 1]
        return AiModelDAO._cache_models

    async def get_model_by_level(self, level: int) -> McAiModel|None:
        """通过 Level 极速查找"""
        await self.list_models()  # 确保缓存已通过类变量更新
        # 统一使用 AiModelDAO 访问类属性
        return AiModelDAO._cache_level_map.get(level)

    async def get_model_name_by_identifier(self, identifier: str) -> str:
        """通过模型标识符极速查找"""
        await self.list_models()
        # 统一使用 AiModelDAO 访问类属性
        model = AiModelDAO._cache_identifier_map.get(identifier)
        return model.model_name if model else "默认模型"
