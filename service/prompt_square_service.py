from fastapi import BackgroundTasks
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from ai.adapters.enums import AIAction
from common.config.get_db import get_db, get_db_context
from common.exception.errors import NotFoundError, ServerError
from common.exception.lzsd_exception import SensitiveWordException, BusinessException
from common.modules.book_exporter import BookExporter
from core.entity.do.prompt_square_do import PromptSquare
from core.entity.do.users_do import User
from core.entity.vo.prompt_square_vo import (
    PromptItem,
    PromptSquareUpdateReq, PromptItemDetail, PromptDetailResp, PromptListItemResp,
    PromptTemplateBriefItem, PromptToolMenuItem,
)
from core.enums.constants import UserCustomPromptStatus
from core.enums.prompt_sys_var import PromptEngineType
from dao.prompt_square_dao import PromptSquareDAO
from service.ai_prompt_service import PromptService
from service.ai_service import AIService
from service.book_service import BookService
from service.content_audit_service import get_content_audit_service

tag_list = ["大纲", "脑洞", "扩写", "金手指", "剧本"]


class PromptSquareService:

    @staticmethod
    def _to_prompt_item(prompt) -> PromptItem:
        return PromptItem.model_validate(prompt, from_attributes=True)

    @staticmethod
    def _to_promp_detail_item(prompt) -> PromptItemDetail:
        return PromptItemDetail.model_validate(prompt, from_attributes=True)

    @staticmethod
    async def get_public_list(
            db: AsyncSession,
            page: int,
            pageSize: int,
            category: str | None = None,
            user_id: int = None,
            promptType: str = "public",  # 新增
            title: str | None = None,
            status:UserCustomPromptStatus | None = None,
            category_filter_field: str = "tags",
            parent_category: str | None = None,
    ):
        """
        获取公开提示词列表
        """

        data, total = await PromptSquareDAO.get_public_list(
            db,
            page,
            pageSize,
            category,
            user_id,
            promptType,
            title,
            status,
            category_filter_field,
            parent_category
        )

        items = []

        for prompt, favor_count, is_favorited in data:
            base = PromptSquareService._to_prompt_item(prompt)

            item = PromptListItemResp(
                **base.model_dump(),
                # 权限
                can_edit=(prompt.author_id == user_id),
                # 新增
                favor_count=favor_count or 0,
                is_favorited=(is_favorited > 0)
            )

            items.append(item)

        return items, total

    @staticmethod
    async def get_public_categories(db: AsyncSession) -> list[str]:
        """
        获取公开提示词分类列表
        """
        categories = await PromptSquareDAO.get_public_categories(db)

        return categories

    @staticmethod
    async def get_tool_menu_list(db: AsyncSession) -> list[PromptToolMenuItem]:
        rows = await PromptSquareDAO.get_tool_menu_list(db)
        return [PromptToolMenuItem(**dict(row)) for row in rows]

    @staticmethod
    async def get_prompt_list_by_category(db: AsyncSession, category: str) -> list[PromptTemplateBriefItem]:
        rows = await PromptSquareDAO.get_prompt_list_by_category(db, category)
        return [PromptTemplateBriefItem(**dict(row)) for row in rows]

    @staticmethod
    async def create_user_prompt(
            db: AsyncSession,
            user_id: int,
            title: str,
            category: str,
            description: str,
            content: str,
            background_tasks: BackgroundTasks
    ) -> PromptItem:
        if category not in tag_list:
            raise BusinessException(message="分类不存在")

        prompt = await PromptSquareDAO.create_user_prompt(db=db, user_id=user_id, title=title, category=category,
                                                          description=description, content=content)
        background_tasks.add_task(
            PromptSquareService.run_audit_in_background,
            prompt.id,
            [title, description, content]
        )
        return PromptSquareService._to_prompt_item(prompt)

    @staticmethod
    # 后台审核
    async def run_audit_in_background(prompt_id: int, texts: list):
        logger.info("后台审核提示词：" + str(texts))

        final_text = ",".join(texts)

        audit_service = get_content_audit_service()
        status = 1
        reason = "审核通过"
        result = await audit_service.audit_user_instruction(text=final_text)
        if not result.passed:
            status = 2
            reason = result.reason

        async with get_db_context() as db:  # 注意：后台任务需要自己开启新的 DB session
            logger.info("后台审核提示词完毕：{}, {}, {}", prompt_id, status, reason)
            await PromptSquareDAO.update_audit_status(db, prompt_id, status, reason)

    @staticmethod
    async def update_user_prompt(
            db: AsyncSession,
            user_id: int,
            req: PromptSquareUpdateReq,
            background_tasks: BackgroundTasks
    ) -> PromptItemDetail | None:
        """
        更新提示词（只能更新自己的）
        """
        prompt = await PromptSquareDAO.get_template_by_key(db, req.template_key)
        if not prompt:
            return None

        # ==================== 权限校验 ====================
        if prompt.author_id != user_id:
            return None  # 或者 raise 权限异常

        if prompt.author_id == 0:
            return None

        # ==================== 执行更新 ====================
        prompt = await PromptSquareDAO.update_user_prompt(db, prompt, req)

        background_tasks.add_task(
            PromptSquareService.run_audit_in_background,
            prompt.id,
            [prompt.title, prompt.description, prompt.content]
        )

        return PromptSquareService._to_promp_detail_item(prompt)

    @staticmethod
    async def get_template_by_key(db: AsyncSession, template_key: str) -> PromptSquare | None:
        entity = await PromptSquareDAO.get_template_by_key(db, template_key)
        if entity.status in [0, 1]:
            entity = None
        return entity

    @staticmethod
    async def get_user_prompt_detail(
            db: AsyncSession,
            user_id: int,
            template_key: str
    ) -> PromptItemDetail | None:
        """
        获取用户自己的提示词详情
        """

        row = await PromptSquareDAO.get_prompt_detail(
            db,
            template_key,
            user_id
        )

        if not row:
            return None

        prompt, favor_count, is_favorited = row

        item = PromptSquareService._to_promp_detail_item(prompt)

        data = item.model_dump()

        # ==================== 内容权限控制 ====================
        if prompt.author_id != user_id:
            data["content"] = ""

        return PromptDetailResp(
            **data,
            can_edit=(prompt.author_id == user_id),

            # 新增
            favor_count=favor_count or 0,
            is_favorited=(is_favorited > 0)
        )

    @staticmethod
    async def delete_user_prompt(
            db: AsyncSession,
            user_id: int,
            template_key: str
    ) -> bool:
        """
        删除提示词（只能删除自己的）
        """

        prompt = await PromptSquareDAO.get_template_by_key(db, template_key)

        if not prompt:
            return False

        # ==================== 权限校验 ====================
        if prompt.author_id != user_id:
            return False

        # ==================== 禁止删除官方 ====================
        if prompt.author_id == 0:
            return False

        # ==================== 执行删除 ====================
        await PromptSquareDAO.delete(db, prompt)

        return True

    @staticmethod
    async def execute_by_template(db: AsyncSession,
                                  level: int,
                                  user: User,
                                  template_key: str,
                                  user_prompt: str,
                                  background_tasks,
                                  inputs: dict | None = None,
                                  bid: str | None = None,
                                  temperature: float | None = None,
                                  max_tokens: float | None = None) -> str:
        tpl = await PromptSquareDAO.get_template_by_key(db, template_key)
        if not tpl or tpl.status != 1:
            raise NotFoundError(msg="提示词模版不存在")

        final_inputs = inputs or {}
        if bid:
            book_service = BookService(db)
            book = await book_service.get_book_by_bid(bid=bid, user_id=user.pkId)
            if not book:
                raise NotFoundError(msg=f"书籍[{bid}]不存在")

            key = "sys_book_info"
            if key in final_inputs:
                nodes = await book_service.get_basic_nodes(bid=bid, user_id=user.pkId) or []
                leaf_ids = [node.id for node in nodes]
                exporter = BookExporter(db)
                book_prompt = await exporter.export_to_markdown(book=book, leaf_node_ids=leaf_ids)
                final_inputs[key] = book_prompt

        try:

            prompt = await PromptService.render_prompt_with_params(
                prompt=tpl.content,
                inputs=final_inputs,
                engine_type=PromptEngineType.from_str(tpl.engine_type))
            frozen_tokens = tpl.freeze_tokens
            final_user_prompt = "\n".join(filter(None, [prompt, user_prompt]))

            ai_service = AIService(db)
            request_id, _ = await ai_service.prepare_and_record_request(
                user=user,
                bid=bid,
                origin_prompt=f"【模版】{tpl.title} 【提示词】{user_prompt}",
                user_prompt=final_user_prompt,
                level=level,
                action_type=AIAction.Execute,
                temperature=temperature,
                correlation=[template_key],
                max_tokens=max_tokens,
                tokenEstimate=frozen_tokens,
                background_tasks=background_tasks
            )
            return request_id

        except Exception as e:
            raise ServerError(msg="AI生成失败:{}".format(e))

    @staticmethod
    async def get_my_favor_list(
            db: AsyncSession,
            user_id: int,
            page: int,
            page_size: int,
            title: str | None = None,
            category: str | None = None
    ):
        """
        我的收藏列表
        """

        records, total = await PromptSquareDAO.list_my_favor(
            db,
            user_id,
            page,
            page_size,
            title,
            category
        )

        result = []

        for favor, prompt, favor_count in records:
            result.append(
                PromptListItemResp(
                    **PromptSquareService._to_prompt_item(prompt).model_dump(),
                    # 权限
                    can_edit=(prompt.author_id == user_id),
                    # 新增
                    favor_count=favor_count or 0,
                    is_favorited=True  # 永远 true
                )
            )

        return result, total

    @staticmethod
    async def favor(db: AsyncSession, user_id: int, template_key: str) -> bool:
        """
        收藏（幂等）
        """

        # 是否已收藏
        exist = await PromptSquareDAO.get_by_user_and_key(db, user_id, template_key)

        if exist:
            return True  # 已收藏，直接返回（幂等）

        await PromptSquareDAO.create(db, user_id, template_key)

        return True

    @staticmethod
    async def unfavor(db: AsyncSession, user_id: int, template_key: str) -> bool:
        """
        取消收藏（幂等）
        """

        await PromptSquareDAO.delete_by_user_and_key(db, user_id, template_key)

        return True
