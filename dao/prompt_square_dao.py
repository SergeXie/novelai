from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import or_
from sqlalchemy.sql.expression import delete, desc
from common.utils.generator import LZSDGenerator
from core.entity.do.prompt_square_do import PromptSquare, UserTemplateFavor
from core.entity.vo.prompt_square_vo import PromptSquareCreateReq, PromptSquareUpdateReq
from core.enums.constants import UserCustomPromptStatus
from core.enums.prompt_sys_var import PromptEngineType, PromptTopCategory


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
            tag: str | None = None,
            user_id: int | None = None,
            promptType: str = "public",
            title: str | None = None,
            status: UserCustomPromptStatus | None = None,
            parent_category: str | None = None,
    ):

        """
        查询：公开 + 自己的 + 收藏信息
        """

        FavorAlias = aliased(UserTemplateFavor)

        if promptType == "mine":
            # 我的发布
            condition = (PromptSquare.author_id == user_id)
        else:
            filter_status = status if status is not None else UserCustomPromptStatus.AVAILABLE
            condition = (PromptSquare.status == filter_status.code)

        if category:
            condition = condition & (PromptSquare.category == category)

        # ==================== 补充 tag 查询开始 ====================
        if tag and tag.strip():
            # 构造形如 "%,tag,%" 的匹配字符串，精准匹配逗号分隔的标签
            like_filter = f"%,{tag.strip()},%"
            # 使用 func.concat 前后补逗号，规避边界匹配漏洞（如 "AI" 错配到 "AIGC"）
            condition = condition & (func.concat(',', PromptSquare.tags, ',').like(like_filter))
        # ==================== 补充 tag 查询结束 ====================

        if title:
            condition = condition & (PromptSquare.title.ilike(f"%{title}%"))

        # 顶级分类限制只用于公开广场；“我的发布”应展示用户自己的全部记录。
        if parent_category and promptType != "mine":
            condition = condition & (PromptSquare.parent_category == parent_category)
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
    async def get_tool_menu_list(db: AsyncSession):
        stmt = (
            select(
                PromptSquare.template_key,
                PromptSquare.title,
                PromptSquare.description,
                PromptSquare.cover_img,
                PromptSquare.content,
                PromptSquare.category,
                PromptSquare.parent_category,
            )
            .where(
                PromptSquare.parent_category == "SCENARIO",
                PromptSquare.status == UserCustomPromptStatus.AVAILABLE.code,
            )
            .order_by(PromptSquare.created_at.desc())
        )

        result = await db.execute(stmt)
        return result.mappings().all()

    @staticmethod
    async def get_prompt_list_by_category(db: AsyncSession, category: str):
        stmt = (
            select(
                PromptSquare.template_key,
                PromptSquare.title,
                PromptSquare.description,
            )
            .where(
                PromptSquare.parent_category == "TEXTEDITIN",
                PromptSquare.category == category,
                PromptSquare.status == UserCustomPromptStatus.AVAILABLE.code,
            )
            .order_by(PromptSquare.created_at.desc())
        )

        result = await db.execute(stmt)
        return result.mappings().all()

    @staticmethod
    async def get_prompt_list_with_filter(
            db: AsyncSession,
            parent_category: PromptTopCategory = None,
            category: str = None,
            tag: str = None
    ):
        # 1. 基础查询语句
        stmt = select(
            PromptSquare.template_key,
            PromptSquare.title,
            PromptSquare.description,
        )

        # 2. 动态构建 where 条件列表
        conditions = [
            # 默认基础条件：状态必须是可用
            PromptSquare.status == UserCustomPromptStatus.AVAILABLE.code
        ]

        # 当 parent_category 不为 None 时拼接条件
        if parent_category is not None:
            conditions.append(PromptSquare.parent_category == parent_category.code)

        # 当 category 不为 None 且不为空字符串时拼接条件
        if category and category.strip():
            # 假设数据库里有 category 字段，这里补上对应的逻辑
            conditions.append(PromptSquare.category == category)

        # 当 tag 不为 None 且不为空字符串时拼接条件
        if tag and tag.strip():
            # 补全模糊匹配的 % 通配符，精准匹配逗号分隔的标签
            like_filter = f"%,{tag.strip()},%"
            conditions.append(func.concat(',', PromptSquare.tags, ',').like(like_filter))

        # 3. 将条件解包传给 where
        stmt = stmt.where(*conditions).order_by(PromptSquare.created_at.desc())

        # 4. 执行并返回
        result = await db.execute(stmt)
        return result.mappings().all()

    @staticmethod
    async def create_user_prompt(
            db: AsyncSession,
            user_id: int,
            title: str,
            category: str,
            description: str,
            content: str,
    ) -> PromptSquare:

        prompt = PromptSquare(
            template_key=LZSDGenerator.generate_template_id(),
            title=title,
            parent_category=PromptTopCategory.CREATION.code,
            category=category,
            content=content,
            description=description,
            status=UserCustomPromptStatus.PENDING.code,
            author_id=user_id,
            cover_img="",
            engine_type=PromptEngineType.JINJA2.value,
            input_schema={},
            use_count=0,
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
    ):
        """
        获取提示词详情（带收藏信息）
        """

        FavorAlias = aliased(UserTemplateFavor)

        stmt = (
            select(
                PromptSquare,
                func.count(UserTemplateFavor.id).label("favor_count"),
                func.count(FavorAlias.id).label("is_favorited")
            )
            # 收藏总数
            .outerjoin(
                UserTemplateFavor,
                UserTemplateFavor.template_key == PromptSquare.template_key
            )
            # 当前用户收藏
            .outerjoin(
                FavorAlias,
                (FavorAlias.template_key == PromptSquare.template_key) & (FavorAlias.user_id == user_id)
            )
            .where(
                PromptSquare.template_key == template_key,
                or_(
                    PromptSquare.author_id == user_id,
                    PromptSquare.author_id == 0,
                    PromptSquare.status == 1
                )
            )
            .group_by(PromptSquare.id)
        )

        result = await db.execute(stmt)
        row = result.first()

        return row  # 👈 注意这里不再是 prompt，而是 tuple

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
        prompt.status = UserCustomPromptStatus.PENDING.code

        db.add(prompt)
        await db.commit()
        await db.refresh(prompt)
        return prompt

    @staticmethod
    async def update_audit_status(
            db: AsyncSession,
            prompt_id: int,
            status: int,
            audit_reason: str = ""
    ) -> bool:
        """
        更新提示词模板的审核状态和原因
        :param prompt_id: 模板ID
        :param status: 状态值 (0:下架, 1:上架, 2:审核中, 3:审核失败)
        :param audit_reason: 审核原因
        """
        stmt = (
            update(PromptSquare)
            .where(PromptSquare.id == prompt_id)
            .values(
                status=status,
                audit_reason=audit_reason
            )
        )
        result = await db.execute(stmt)
        # 记得在调用方执行 db.commit()，或者在此处执行
        # await db.commit()
        return result.rowcount > 0

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
            title: str,
            category: str
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
