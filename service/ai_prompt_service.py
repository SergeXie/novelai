from typing import List, Optional, Union

from jinja2 import Environment
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from common.exception.errors import NotFoundError
from core.entity.do.book_node import BookNode
from core.entity.do.books import Book
from core.entity.do.prompt_register import PromptRegistry
from core.entity.vo.prompt_register_vo import PromptRegistryResp
from core.enums.node_type import BookNodeCategory
from core.enums.prompt_sys_var import PromptEngineType
from dao.ai_prompt_registry_dao import PromptRegistryDAO
from dao.prompt_square_dao import PromptSquareDAO

jinja_env = Environment(enable_async=True)

class PromptService:
    def __init__(self, db: AsyncSession):
        self.dao = PromptRegistryDAO(db)
        self.db = db

    async def get_all_prompts(self):
        """获取所有记录的原始逻辑"""
        return await self.dao.get_template_prompts()

    async def get_scope_detail_prompts(self, scope:int) -> List[PromptRegistry]:
        return await self.dao.get_prompts_detail_scope(scope)

    async def get_detail_by_key(self, tool_key: str) -> Optional[PromptRegistry]:
        """根据key获取详情"""
        return await self.dao.get_by_tool_key(tool_key)

    async def get_book_creation_templates(self) -> dict:
        """
        获取创建作品时候用到的ai提示词模板
        """
        data = dict()

        tool_keys = ["wenyuan_title_forge", "wenyuan_blurb_forge"]
        rets = await PromptSquareDAO.get_active_templates_by_keys(
            db=self.db,
            template_keys=tool_keys,
        )
        for tool in rets:
            prompt = PromptRegistryResp.model_validate(dict(tool))
            if prompt.tool_key == tool_keys[0]:
                data["title"] = prompt
            elif prompt.tool_key == tool_keys[1]:
                data["intro"] = prompt

        return data

    async def generate_prompt_by_nodes(self, user_id: int, bid: str, ids: list) -> str:
        """
        入口方法：负责异步数据库检索
        """
        if not ids:
            return ""

        # 只查询必要的字段
        result = await self.db.execute(
            select(BookNode.type, BookNode.name, BookNode.content)
            .where(and_(
                BookNode.id.in_(ids),
                BookNode.uid == user_id,
                BookNode.bid == bid
            )).order_by(BookNode.id.asc())
        )
        nodes = result.all()
        return self._assemble_prompt(list(nodes))

    @staticmethod
    async def generate_book_base_prompt(book:Book) -> str:
        prompt_segments = []
        # --- 第一部分：书籍全局背景 (置顶) ---
        if book.title:
            prompt_segments.append(f"# 书名\n{book.title}")
        if book.description:
            prompt_segments.append(f"# 简介\n{book.description}")

        return "\n\n".join(prompt_segments)

    async def generate_book_global_prompt(self, book:Book) -> str:
        node_result = await self.db.execute(
            select(BookNode.type, BookNode.name, BookNode.content)
            .where(and_(
                BookNode.type in (BookNodeCategory.ROLES, BookNodeCategory.WORLDVIEW, BookNodeCategory.WRITING_STYLE),
                BookNode.bid == book.bid
            )).order_by(BookNode.type.asc())
        )
        nodes = node_result.all()
        return self._assemble_prompt(list(nodes))

    @staticmethod
    def _assemble_prompt(nodes: List) -> str:
        """
        核心逻辑：基于枚举进行结构化拼装
        """
        if not nodes:
            return ""

        # 1. 使用枚举作为 Key 进行分类聚合
        # 初始化桶，确保即使某类没有节点，逻辑也不会报错
        grouped = {cat: [] for cat in BookNodeCategory}

        for node in nodes:
            # 使用你定义的 from_code 转换安全获取枚举项
            category = BookNodeCategory.from_code(node.type)
            grouped[category].append(node)

        prompt_segments = []

        # 2. 拼装【设定类】 (角色、世界观、写作手法、自定义)
        # 按照逻辑顺序：角色卡 -> 世界观 -> 写作手法 -> 自定义
        setting_order = [
            BookNodeCategory.ROLES,
            BookNodeCategory.WORLDVIEW,
            BookNodeCategory.WRITING_STYLE,
            BookNodeCategory.NORMAL
        ]

        for cat in setting_order:
            items = grouped.get(cat, [])
            if items:
                # 使用枚举的 .key 获取显示名称 (如 "角色卡")
                header = f"## {cat.key}列表" if cat == BookNodeCategory.ROLES else f"## {cat.key}"
                # 拼接：【名称】内容 或 直接内容
                body = "\n".join([f"【{n.name}】{n.content}" if n.name else n.content for n in items])
                prompt_segments.append(f"{header}\n{body}")

        # 3. 拼装【正文类】 (作为前情提要)
        content_items = grouped.get(BookNodeCategory.CONTENT, [])
        if content_items:
            chapters = []
            for n in content_items:
                title = f"### {n.name}" if n.name else "### 未命名章节"
                chapters.append(f"{title}\n{n.content}")

            prompt_segments.append("## 前情提要\n" + "\n\n".join(chapters))

        return "\n\n".join(prompt_segments)

    async def render_prompt_tool(self, book:Optional[Book], templateKey: str, inputs: dict) -> str:
        # 1. 获取模板配置
        isRelated = 1
        config = await self.dao.get_active_by_key(templateKey)
        if not config:
            raise NotFoundError(msg=f"Template [{templateKey}] 未找到或已禁用")

        try:
            final_content = await self.render_prompt_with_params(prompt=config.content,
            inputs=inputs,
            engine_type=PromptEngineType.from_str(config.engine_type))
            final_content = final_content.strip()

            # 3. 关联背景信息拼接 (优化点：将基本信息与节点信息合并)
            if isRelated and book is not None:
                book_basic_prompt = await self.generate_book_base_prompt(book=book)
                book_global_prompt = await self.generate_book_global_prompt(book=book)
                # 拼接顺序：背景设定 -> 前情提要 -> 当前任务指令(渲染后的 template_str)
                final_content = f"{book_basic_prompt.strip()}\n\n{book_global_prompt.strip()}\n\n{final_content}"

            return final_content

        except Exception as e:
            raise e

    @staticmethod
    async def render_prompt_with_params(prompt:str, inputs: dict, engine_type:PromptEngineType = PromptEngineType.JINJA2) -> str:
        final_content = ""
        try:
            if engine_type == PromptEngineType.JINJA2:
                template = jinja_env.from_string(prompt)
                final_content = await template.render_async(**inputs)
            elif engine_type == PromptEngineType.FSTRING:
                # 使用 format 的安全变体，防止 inputs 缺少 key 时崩溃
                final_content = prompt.format_map(inputs)

            return final_content.strip()
        except Exception as _:
            raise ValueError(f"模板变量替换出错，请检查输入参数")

