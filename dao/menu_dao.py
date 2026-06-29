from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.entity.do.mc_menu_do import McMenu, McModule


class MenuDAO:
    @staticmethod
    async def list_categories_by_module(db: AsyncSession, module_key: str):
        stmt = (
            select(
                McMenu.id,
                McMenu.name,
                McMenu.key,
                McMenu.weight,
                McMenu.interaction_type
            )
            .join(McModule, McModule.module_key == McMenu.module_key)
            .where(
                McModule.module_key == module_key,
                McMenu.status == 1,
            )
            .order_by(McMenu.weight.desc(), McMenu.id.asc())
        )

        result = await db.execute(stmt)
        return result.mappings().all()
