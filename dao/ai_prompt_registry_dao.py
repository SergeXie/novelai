from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.entity.do.mc_menu_do import McMenu
from core.entity.do.prompt_register import PromptRegistry
from core.entity.do.prompt_square_do import PromptSquare


class PromptRegistryDAO:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_prompts(self,  only_active: bool = True) -> List[PromptRegistry]:
        """
        获取全部提示词模板。
        """
        stmt = select(PromptRegistry)

        if only_active:
            stmt = stmt.where(PromptRegistry.status == 1)

        stmt = stmt.order_by(PromptRegistry.id.desc())

        result = await self.db.execute(stmt)
        return list(result.scalars().all())


    async def get_all_prompts_scope(self, only_active: bool = True) -> List[PromptRegistry]:
        """
        获取全部提示词模板。
        """
        stmt = select(PromptRegistry)

        if only_active:
            stmt = stmt.where(and_(PromptRegistry.status == 1, PromptRegistry.scope == "1"))

        stmt = stmt.order_by(PromptRegistry.id.desc())

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_prompts_detail_scope(self, scope: int) -> List[PromptRegistry]:
        """
        获取指定的scope提示词模板
        """

        stmt = select(PromptRegistry)

        stmt = stmt.where(and_(PromptRegistry.status == 1, PromptRegistry.scope == scope))

        stmt = stmt.order_by(PromptRegistry.id.desc())

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_tool_key(self, tool_key: str) -> Optional[PromptRegistry]:
        """
        根据 tool_key 获取唯一的提示词配置
        """
        stmt = select(PromptRegistry).where(PromptRegistry.tool_key == tool_key)

        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_active_by_key(self, templateKey: str) -> Optional[PromptRegistry]:
        """
        获取正在启用的指定工具配置（业务最常用）
        """
        stmt = select(PromptSquare).where(
            PromptSquare.template_key == templateKey,
            PromptSquare.status == 1
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_active_by_is_related(db: AsyncSession, name: str) -> Optional[PromptRegistry]:
        """
        获取正在启用的指定工具配置（业务最常用）
        """
        stmt = select(PromptRegistry).where(
            PromptRegistry.name == name,
            PromptRegistry.status == 1
        )
        result = await db.execute(stmt)
        return result.scalars().first()
