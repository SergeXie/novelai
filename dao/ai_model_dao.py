from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.entity.do.mc_ai_model import McAiModel


class AiModelDAO:

    @staticmethod
    async def list_models(
        db: AsyncSession,
        *,
        only_enabled: bool = True,
    ) -> list[McAiModel]:
        """
        获取模型列表
        """
        stmt = select(McAiModel)

        if only_enabled:
            stmt = stmt.where(McAiModel.status == 1)

        stmt = stmt.order_by(McAiModel.level.asc())

        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def first_ai_models(db: AsyncSession, level: int):
        stmt = select(McAiModel.multiplier).where(McAiModel.level == level)
        result = await db.execute(stmt)
        multiplier = result.scalars().first()
        return multiplier

