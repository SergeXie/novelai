from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import or_
from sqlalchemy.sql.expression import delete, desc

from common.utils.generator import LZSDGenerator
from core.entity.do.prompt_square_do import PromptSquare, UserTemplateFavor
from core.entity.vo.prompt_square_vo import PromptSquareCreateReq, PromptSquareUpdateReq
from core.enums.prompt_sys_var import PromptEngineType


class PromptSquareDAO:

    @staticmethod
    def _public_condition(category: str | None = None, user_id: int = None):
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
            category: str | None = None,
            user_id: int | None = None,
            promptType:str = "public",
            title: str | None = None,
    ):

        """
        查询：公开 + 自己的 + 收藏信息
        """

        FavorAlias = aliased(UserTemplateFavor)

        if promptType == "mine":
            # 我的发布
            condition = (PromptSquare.author_id == user_id)

        else:
            # 公开广场
            condition = (PromptSquare.status == 1)

        if category:
            condition = condition & (PromptSquare.category == category)

        if title:
            condition = condition & (PromptSquare.title.ilike(f"%{title}%"))
        # ==================== 主查询 ====================

        stmt = (
            select(
                PromptSquare,
                func.count(UserTemplateFavor.id).label("favor_count"),
                func.count(FavorAlias.id).label("is_favorited")  # 是否收藏
            )
            # 收藏总数
            .outerjoin(
                UserTemplateFavor,
                UserTemplateFavor.template_key == PromptSquare.template_key
            )
            # 当前用户收藏
            .outerjoin(
                FavorAlias,
                (FavorAlias.template_key == PromptSquare.template_key) &
                (FavorAlias.user_id == user_id)
            )
            .where(condition)
            .group_by(PromptSquare.id)
            .order_by(
                (PromptSquare.author_id == user_id).desc(),
                PromptSquare.created_at.desc()
            )
            .offset((page - 1) * pageSize)
            .limit(pageSize)
        )

        result = await db.execute(stmt)
        rows = result.all()

        # ==================== 总数 ====================

        total_stmt = select(func.count()).where(condition)
        total = (await db.execute(total_stmt)).scalar()

        return rows, total

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
            template_key=LZSDGenerator.generate_template_id(),
            title=req.title,
            category=req.category,
            content=req.content,
            description=req.description,
            status=req.status,
            author_id=user_id,
            cover_img="",
            engine_type=PromptEngineType.JINJA2.value,
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
            template_key: str,
            user_id: int
    ) -> PromptSquare | None:
        stmt = select(PromptSquare).where(
            PromptSquare.template_key == template_key,
            PromptSquare.author_id == user_id
        )

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_template_by_key(
            db: AsyncSession,
            template_key: str
    ) -> PromptSquare | None:
        stmt = select(PromptSquare).where(
            PromptSquare.template_key == template_key
        )

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_prompt_detail(
            db: AsyncSession,
            template_key: str,
            user_id: int
    ) -> PromptSquare | None:
        """
        获取提示词详情（支持公开 / 官方 / 自己）
        """

        stmt = select(PromptSquare).where(
            PromptSquare.template_key == template_key,
            or_(
                PromptSquare.author_id == user_id,  # 自己
                PromptSquare.author_id == 0,  # 官方
                PromptSquare.status == 1  # 已上架
            )
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

    @staticmethod
    async def delete(
            db: AsyncSession,
            prompt: PromptSquare
    ):
        await db.delete(prompt)
        await db.commit()

    @staticmethod
    async def get_by_user_and_key(
            db: AsyncSession,
            user_id: int,
            template_key: str
    ) -> UserTemplateFavor | None:

        stmt = select(UserTemplateFavor).where(
            UserTemplateFavor.user_id == user_id,
            UserTemplateFavor.template_key == template_key
        )

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_my_favor(
            db: AsyncSession,
            user_id: int,
            page: int,
            page_size: int,
            title:str,
            category:str
    ):
        """
        查询我的收藏（带收藏数）
        """

        conditions = [UserTemplateFavor.user_id == user_id]

        if title:
            conditions.append(PromptSquare.title.ilike(f"%{title}%"))

        if category:
            conditions.append(PromptSquare.category == category)


        FavorAlias = aliased(UserTemplateFavor)

        stmt = (
            select(
                UserTemplateFavor,
                PromptSquare,
                func.count(FavorAlias.id).label("favor_count")
            )
            # 当前用户收藏
            .join(
                PromptSquare,
                UserTemplateFavor.template_key == PromptSquare.template_key
            )
            # 所有用户收藏（统计）
            .outerjoin(
                FavorAlias,
                FavorAlias.template_key == PromptSquare.template_key
            ).where(*conditions)
            .where(UserTemplateFavor.user_id == user_id)
            .group_by(UserTemplateFavor.id, PromptSquare.id)
            .order_by(desc(UserTemplateFavor.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await db.execute(stmt)
        rows = result.all()

        # ==================== 总数 ====================

        count_stmt = select(func.count()).where(
            UserTemplateFavor.user_id == user_id
        )
        total = (await db.execute(count_stmt)).scalar()

        return rows, total

    @staticmethod
    async def create(
            db: AsyncSession,
            user_id: int,
            template_key: str
    ):
        favor = UserTemplateFavor(
            user_id=user_id,
            template_key=template_key
        )

        db.add(favor)

        try:
            await db.commit()
        except Exception:
            await db.rollback()  # 防止唯一索引冲突

    @staticmethod
    async def delete_by_user_and_key(
            db: AsyncSession,
            user_id: int,
            template_key: str
    ):
        stmt = delete(UserTemplateFavor).where(
            UserTemplateFavor.user_id == user_id,
            UserTemplateFavor.template_key == template_key
        )

        await db.execute(stmt)
        await db.commit()

