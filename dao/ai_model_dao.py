import asyncio
from types import SimpleNamespace
from typing import Dict, List

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.adapters.enums import AIProvider
from core.entity.do.ai_model import McAiModel


class AiModelDAO:
    _cache_models: List[SimpleNamespace] | None = None
    _cache_level_map: Dict[int, SimpleNamespace] = {}
    _cache_identifier_map: Dict[str, SimpleNamespace] = {}
    config_map: Dict[AIProvider, SimpleNamespace] = {}
    _cache_lock = asyncio.Lock()

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

    async def _load_models_once(self) -> None:
        if AiModelDAO._cache_models is not None:
            return

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
            # 键值对 例如 AIProvider.FREE: settings.free,
            AiModelDAO.config_map = {
                AIProvider.parse(model.level): model
                for model in all_models
            }

            logger.info(f"AI model config_map loaded from database. count={len(all_models)}")
        except Exception as e:
            logger.error(f"Failed to load AI model config_map: {e}")
            AiModelDAO._cache_models = []
            AiModelDAO._cache_level_map = {}
            AiModelDAO._cache_identifier_map = {}
            AiModelDAO.config_map = {}

    async def refresh_models_cache(self) -> dict:
        """Reload model config from database and replace the in-memory cache."""
        async with AiModelDAO._cache_lock:
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
            AiModelDAO.config_map = {
                AIProvider.parse(model.level): model
                for model in all_models
            }

        enabled_count = len([model for model in all_models if model.status == 1])
        logger.info(
            f"AI model config_map refreshed from database. total={len(all_models)}, enabled={enabled_count}"
        )
        return {
            "total": len(all_models),
            "enabled": enabled_count,
        }

    async def list_models(self, only_enabled: bool = True) -> list[SimpleNamespace]:
        await self._load_models_once()

        models = AiModelDAO._cache_models or []
        if only_enabled:
            return [model for model in models if model.status == 1]

        return models

    async def get_model_by_level(self, level: int) -> SimpleNamespace | None:
        await self.list_models()
        return AiModelDAO._cache_level_map.get(level)

    async def get_model_by_provider(self, provider: AIProvider) -> SimpleNamespace | None:
        await self.list_models()
        return AiModelDAO.config_map.get(provider)

    async def get_model_name_by_identifier(self, identifier: str) -> str:
        await self.list_models()
        model = AiModelDAO._cache_identifier_map.get(identifier)
        return model.model_name if model else "默认模型"
