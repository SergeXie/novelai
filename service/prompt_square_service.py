from sqlalchemy.ext.asyncio import AsyncSession

from core.entity.vo.prompt_square_vo import (
    PromptItem,
    PromptCategoryItem,
    PromptSquareCreateReq,
    PromptSquareUpdateReq,
)
from dao.prompt_square_dao import PromptSquareDAO


class PromptSquareService:

    @staticmethod
    def _to_prompt_item(prompt) -> PromptItem:
        return PromptItem.model_validate(prompt, from_attributes=True)

    @staticmethod
    async def get_public_list(
        db: AsyncSession,
        page: int,
        pageSize: int,
        category: str | None = None
    ):
        """
        获取公开提示词列表
        """

        data, total = await PromptSquareDAO.get_public_list(
            db,
            page,
            pageSize,
            category
        )

        # 转 schema
        items = [PromptSquareService._to_prompt_item(i) for i in data]

        return items, total

    @staticmethod
    async def get_public_categories(db: AsyncSession):
        """
        获取公开提示词分类列表
        """
        categories = await PromptSquareDAO.get_public_categories(db)

        return [category for category in categories if category]

    @staticmethod
    async def create_user_prompt(
        db: AsyncSession,
        user_id: int,
        req: PromptSquareCreateReq
    ) -> PromptItem:
        prompt = await PromptSquareDAO.create_user_prompt(db, user_id, req)
        return PromptSquareService._to_prompt_item(prompt)

    @staticmethod
    async def update_user_prompt(
        db: AsyncSession,
        user_id: int,
        req: PromptSquareUpdateReq
    ) -> PromptItem | None:
        prompt = await PromptSquareDAO.get_user_prompt_by_id(db, req.id, user_id)
        if not prompt:
            return None

        prompt = await PromptSquareDAO.update_user_prompt(db, prompt, req)
        return PromptSquareService._to_prompt_item(prompt)
