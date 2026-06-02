import time
from types import SimpleNamespace
from typing import Dict, List

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.entity.do.ai_model import McAiModel


class AiModelDAO:
    _cache_models: List[SimpleNamespace] | None = None
    _cache_level_map: Dict[int, SimpleNamespace] = {}
    _cache_identifier_map: Dict[str, SimpleNamespace] = {}
    _last_update: float = 0
    CACHE_TTL = 1800

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _snapshot_model(model: McAiModel) -> SimpleNamespace:
        # Cache scalar snapshots, not ORM instances, so cached data is session-independent.
        return SimpleNamespace(
            id=model.id,
            level=model.level,
            model_name=model.model_name,
            model_identifier=model.model_identifier,
            provider=model.provider,
            multiplier=model.multiplier,
            max_tokens=model.max_tokens,
            temperature=model.temperature,
            context_window=model.context_window,
            base_url=model.base_url,
            api_key=model.api_key,
            weight=model.weight,
            status=model.status,
            createTime=model.createTime,
            updateTime=model.updateTime,
        )

    async def list_models(self, only_enabled: bool = True) -> list[SimpleNamespace]:
        now = time.time()

        if AiModelDAO._cache_models is None or (now - AiModelDAO._last_update) > AiModelDAO.CACHE_TTL:
            try:
                stmt = select(McAiModel).order_by(McAiModel.weight.desc())
                result = await self.db.execute(stmt)
                all_models = [
                    AiModelDAO._snapshot_model(model)
                    for model in result.scalars().all()
                ]

                AiModelDAO._cache_models = all_models
                AiModelDAO._cache_level_map = {model.level: model for model in all_models}
                AiModelDAO._cache_identifier_map = {
                    model.model_identifier: model
                    for model in all_models
                }
                AiModelDAO._last_update = now

                logger.info(f"AI model cache rebuilt. count={len(all_models)}")
            except Exception as e:
                logger.error(f"Failed to refresh AI model cache: {e}")
                return []

        models = AiModelDAO._cache_models or []
        if only_enabled:
            return [model for model in models if model.status == 1]

        return models

    async def get_model_by_level(self, level: int) -> SimpleNamespace | None:
        await self.list_models()
        return AiModelDAO._cache_level_map.get(level)

    async def get_model_name_by_identifier(self, identifier: str) -> str:
        await self.list_models()
        model = AiModelDAO._cache_identifier_map.get(identifier)
        return model.model_name if model else "默认模型"
