from typing import List, Optional, Any
from jinja2 import Template
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from common.config.get_db import get_db_context
from core.entity.do.prompt_register import PromptRegistry
from dao.ai_prompt_registry_dao import PromptRegistryDAO
from dao.book_dao import BookDAO


class PromptService:
    def __init__(self, db: AsyncSession):
        self.dao = PromptRegistryDAO(db)
        self.db = db

    async def get_all_prompts(self) -> List[PromptRegistry]:
        """获取所有记录的原始逻辑"""
        return await self.dao.get_all_prompts()

    async def get_detail_by_key(self, tool_key: str) -> Optional[PromptRegistry]:
        """根据key获取详情"""
        return await self.dao.get_by_tool_key(tool_key)

    async def render_prompt_content(self, bid: str, user_id:int, tool_key: str, inputs: dict) -> str:
        # 提示词拼接
        nodes_contents = await BookDAO.get_book_nodes_list(self.db, [], user_id, bid, interface_name="render")

        input_user_prompt = "\n".join(nodes_contents) + "\n"

        # 1. 获取模板配置
        config = await self.dao.get_active_by_key(tool_key)
        if not config:
            raise ValueError(f"Template [{tool_key}] not found or inactive")

        # 2. 准备渲染环境
        template_str = config.template_content

        # 3. 渲染逻辑
        if config.engine_type == "jinja2":
            # 对于 4G 服务器，建议对复杂模板使用异步渲染或限制超时
            from jinja2 import Environment, meta
            env = Environment(enable_async=True)
            template = env.from_string(template_str)
            template_str = await template.render_async(**inputs)

        elif config.engine_type == "fstring":
            template_str = template_str.format(**inputs)


        return input_user_prompt + template_str