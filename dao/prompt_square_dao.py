from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from common.config.generator import LZSDGenerator
from core.entity.do.prompt_square_do import PromptSquare
from core.entity.vo.prompt_square_vo import PromptSquareCreateReq, PromptSquareUpdateReq


class PromptSquareDAO:

    @staticmethod
    def _public_condition(category: str | None = None):
        condition = (
            (PromptSquare.author_id == 0) &
            (PromptSquare.status == 1)
        )
        if category:
            condition = condition & (PromptSquare.category == category)
        return condition

    @staticmethod
    async def get_public_list(
        db: AsyncSession,
        page: int,
        pageSize: int,
        category: str | None = None
    ):
        """
        查询公开提示词（author_id=0）
        """

        # ==================== 条件 ====================

        condition = PromptSquareDAO._public_condition(category)

        # ==================== 总数 ====================

        total_stmt = select(func.count()).where(condition)
        total = (await db.execute(total_stmt)).scalar()

        # ==================== 分页 ====================

        stmt = (
            select(PromptSquare)
            .where(condition)
            .order_by(PromptSquare.created_at.desc())
            .offset((page - 1) * pageSize)
            .limit(pageSize)
        )

        result = await db.execute(stmt)
        data = result.scalars().all()

        return data, total

    @staticmethod
    async def get_public_categories(db: AsyncSession):
        """
        查询公开提示词的分类列表，并按分类去重
        """
        stmt = (
            select(PromptSquare.category)
            .where(PromptSquareDAO._public_condition())
            .group_by(PromptSquare.category)
            .order_by(func.max(PromptSquare.created_at).desc())
        )

        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def create_user_prompt(
        db: AsyncSession,
        user_id: int,
        req: PromptSquareCreateReq
    ) -> PromptSquare:
        prompt = PromptSquare(
            template_key=LZSDGenerator.generate_request_id(),
            title=req.title,
            category=req.category,
            content=req.content,
            description=req.description,
            status=req.status,
            author_id=user_id,
            cover_img="",
            tags=None,
            engine_type="jinja2",
            input_schema={},
            use_count=0
        )

        db.add(prompt)
        await db.commit()
        await db.refresh(prompt)
        return prompt

    @staticmethod
    async def get_user_prompt_by_id(
        db: AsyncSession,
        prompt_id: int,
        user_id: int
    ) -> PromptSquare | None:
        stmt = select(PromptSquare).where(
            PromptSquare.id == prompt_id,
            PromptSquare.author_id == user_id
        )

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def update_user_prompt(
        db: AsyncSession,
        prompt: PromptSquare,
        req: PromptSquareUpdateReq
    ) -> PromptSquare:
        prompt.title = req.title
        prompt.category = req.category
        prompt.content = req.content
        prompt.description = req.description
        prompt.status = req.status

        db.add(prompt)
        await db.commit()
        await db.refresh(prompt)
        return prompt
