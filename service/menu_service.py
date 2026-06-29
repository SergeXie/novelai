from sqlalchemy.ext.asyncio import AsyncSession

from core.enums.constants import MenuModuleKey
from core.entity.vo.menu_vo import MenuCategoryItem
from dao.menu_dao import MenuDAO


class MenuService:
    @staticmethod
    async def list_creation_categories(db: AsyncSession) -> list[MenuCategoryItem]:
        rows = await MenuDAO.list_categories_by_module(db, MenuModuleKey.CREATION_TOOLS.value)
        return [
            MenuCategoryItem(id=row["id"], name=row["name"], key=row["key"], interaction_type=row["interaction_type"])
            for row in rows
        ]

    @staticmethod
    async def list_prompt_square_labels(db: AsyncSession) -> list[str]:
        rows = await MenuDAO.list_categories_by_module(db, MenuModuleKey.PROMT_SQUARE_LABELS.value)
        return [
            MenuCategoryItem(id=row["id"], name=row["name"], key=row["key"], interaction_type=row["interaction_type"])
            for row in rows
        ]
