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
            input_price=model.input_price,
            output_price=model.output_price,
            sale_multiplier=model.sale_multiplier,
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
        AiModelDAO._cache_models = None
        await self._load_models_once()

    async def list_models_with_cache(self, only_enabled: bool = True) -> list[SimpleNamespace]:
        await self._load_models_once()

        models = AiModelDAO._cache_models or []
        if only_enabled:
            return [model for model in models if model.status == 1]

        return models

    async def list_models(self, only_enabled: bool = True) -> list[SimpleNamespace]:
        """实时从数据库获取最新的模型列表，不再走内存缓存"""
        # 1. 构造过滤条件（逻辑删除）与排序规则（按权重降序排列，保持与 refresh 逻辑一致）
        stmt = (
            select(McAiModel)
            .order_by(McAiModel.weight.desc())
        )

        # 如果要求只返回启用的模型，直接在 SQL 层面进行过滤，效率更高
        if only_enabled:
            stmt = stmt.where(McAiModel.status == 1)

        # 2. 执行数据库查询
        result = await self.db.execute(stmt)

        # 3. 将 ORM 模型对象转换为与原系统兼容的脱钩快照对象 (SimpleNamespace)
        models = [
            AiModelDAO._snapshot_model(model)
            for model in result.scalars().all()
        ]

        return models

    async def get_model_by_level(self, level: int) -> SimpleNamespace | None:
        await self.list_models()
        ret = AiModelDAO._cache_level_map.get(level)
        if not ret:
            stmt = (
                select(McAiModel)
                .where(McAiModel.level == level)
                .where(McAiModel.status == 1)
            )
            result = await self.db.execute(stmt)
            model = result.scalar_one_or_none()
            if not model:
                return None
            ret = model

        return AiModelDAO._snapshot_model(ret)


    async def get_model_by_provider(self, provider: AIProvider) -> SimpleNamespace | None:
        await self.list_models()
        return AiModelDAO.config_map.get(provider)

    async def get_model_name_by_identifier(self, identifier: str) -> str:
        await self.list_models()
        model = AiModelDAO._cache_identifier_map.get(identifier)
        return model.model_name if model else "默认模型"

    async def get_model_by_identifier(self, identifier: str) -> SimpleNamespace | None:
        await self.list_models()
        model = AiModelDAO._cache_identifier_map.get(identifier)
        if model:
            return model

        stmt = (
            select(McAiModel)
            .where(McAiModel.model_identifier == identifier)
            .where(McAiModel.status == 1)
        )
        result = await self.db.execute(stmt)
        orm_model = result.scalar_one_or_none()
        return AiModelDAO._snapshot_model(orm_model) if orm_model else None

    async def get_all_models_by_level(self, level: int) -> list[SimpleNamespace]:
        """获取指定 level 下的全部模型（含启用和禁用），按 weight 降序"""
        await self.list_models(only_enabled=False)
        models = AiModelDAO._cache_models or []
        return [m for m in models if m.level == level]

    async def update_model_status(self, model_id: int, new_status: int) -> bool:
        """
        更新模型的 status 字段

        Args:
            model_id: 模型 id
            new_status: 新状态 (1=启用, 0=禁用)

        Returns:
            是否更新成功
        """
        try:
            stmt = (
                select(McAiModel)
                .where(McAiModel.id == model_id)
                .limit(1)
            )
            result = await self.db.execute(stmt)
            model = result.scalar_one_or_none()

            if not model:
                logger.warning(f"[模型测试] 更新 status 失败: 未找到 id={model_id} 的模型")
                return False

            old_status = model.status
            model.status = new_status
            await self.db.commit()

            logger.info(
                f"[模型测试] 模型 id={model_id} name={model.model_name} "
                f"status: {old_status} -> {new_status}"
            )
            return True

        except Exception as e:
            await self.db.rollback()
            logger.error(f"[模型测试] 更新模型 status 失败: id={model_id} error={e}")
            return False
