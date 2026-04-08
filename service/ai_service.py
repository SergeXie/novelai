import uuid
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from ai.adapters.enums import AIProvider
from ai.ai_nexus import get_ai_nexus
from common.config.generator import LZSDGenerator
from common.config.get_db import get_db_context
from core.entity.do.users_do import User
from dao.ai_log_dao import AILogDAO
from dao.ai_model_dao import AiModelDAO
from service.usage_service import UsageService


class AIService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_models(self, only_enabled: bool = True):
        """
        获取模型列表
        """
        aimodel_dao = AiModelDAO(self.db)
        return await aimodel_dao.list_models(
            only_enabled=only_enabled,
        )

    async def delete_history(self, uid: int, request_ids: list):
        await AILogDAO.logic_delete(
            db=self.db,
            uid=uid,
            request_ids=request_ids
        )

        return True

    async def prepare_and_record_request(
            self,
            user: User,
            bid: str,
            origin_prompt: str,
            user_prompt: str,
            level: int,
            temperature: float,
            action_type:str,
            correlation=None,
            background_tasks=None
    )->str:
        """
        第一阶段：校验、记录、生成请求ID (同步执行，快速返回)
        """
        user_id = user.pkId


        request_id = LZSDGenerator.generate_request_id(sign=user.account)
        if correlation is None:
            correlation = []

        usage_service = UsageService(self.db)
        await usage_service.check_quota_or_raise(
            user_info=user,
            frozen_token_length=len(user_prompt)
        )

        ai_provider = AIProvider.from_level(level)
        input_user_prompt = user_prompt

        await usage_service.record(
            user_id=user_id,
            request_id=request_id,
            level=level,
            node_ids=correlation,
            bid=bid,
            origin_prompt=origin_prompt,
            system_prompt="",
            user_prompt=input_user_prompt,
            temperature=temperature,
            output_content="",
            action_type=action_type,
        )

        if background_tasks is not None:
            background_tasks.add_task(
                async_generate_task,
                ai_provider,
                input_user_prompt,
                temperature=temperature,
                request_id=request_id,
            )

        return request_id


def _should_retry_with_level2(error: Exception) -> bool:
    """
    命中特定 Gemini 渠道/模型不可用错误时，降级到 level=2 重试
    """
    error_text = str(error)
    return (
        "model_not_found" in error_text
        and "No available channel for model" in error_text
        and "gemini" in error_text.lower()
    )


async def async_generate_task(ai_provider, input_user_prompt, temperature, request_id):
    """后台异步执行 AI 调用并更新结果"""
    system_prompt, output_prompt = "", ""
    try:
        nexus = get_ai_nexus()
        try:
            system_prompt, output_prompt = await nexus.generate_novel_text(
                provider=ai_provider,
                user_prompt=input_user_prompt,
                temperature=temperature
            )
        except Exception as e:
            if _should_retry_with_level2(e):
                fallback_provider = AIProvider.from_level(2)
                logger.warning(
                    f"Request {request_id} 命中特定 Gemini 渠道错误，改用 level=2 重试。原始错误: {e}"
                )
                system_prompt, output_prompt = await nexus.generate_novel_text(
                    provider=fallback_provider,
                    user_prompt=input_user_prompt,
                    temperature=temperature
                )
            else:
                raise

        status = 1  # 成功
    except Exception as e:
        output_prompt = f"Error: {str(e)}"
        status = 0  # 失败
        logger.error(f"Async Generation Error for {request_id}: {output_prompt}")

    async with get_db_context() as db:
        usage_service = UsageService(db=db)
        await usage_service.update_output_content_by_request_id(request_id, output_prompt)