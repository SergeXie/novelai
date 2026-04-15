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
        """基础方法：获取并缓存所有模型"""
        now = time.time()
        if not self._cache_models or (now - self._last_update) > self.CACHE_TTL:
            try:
                # 从数据库拉取全量数据
                stmt = select(McAiModel).order_by(McAiModel.weight.desc())
                result = await self.db.execute(stmt)
                all_models = list(result.scalars().all())

                # 更新主列表缓存
                self._cache_models = all_models
                # 构建内存索引（Key-Value 映射）
                self._cache_level_map = {m.level: m for m in all_models}
                self._cache_identifier_map = {m.model_identifier: m for m in all_models}  # 假设字段名为 model

                self._last_update = now
                logger.info("AI模型内存索引已重建")
            except Exception as e:
                logger.error(f"刷新模型缓存失败: {e}")
                return []

        if only_enabled:
            return [m for m in self._cache_models if m.status == 1]
        return self._cache_models

    async def get_model_by_level(self, level: int) -> McAiModel:
        """通过 Level 极速查找"""
        await self.list_models()  # 确保缓存有效
        return self._cache_level_map.get(level)

    async def get_model_name_by_identifier(self, identifier: str) -> str:
        """通过模型标识符（如 'gpt-4'）极速查找"""
        await self.list_models()  # 确保缓存有效
        model = self._cache_identifier_map.get(identifier)
        return model.model_name if model else "默认模型"


