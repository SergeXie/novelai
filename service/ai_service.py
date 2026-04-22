import textwrap

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from ai.adapters.enums import AIProvider, AIAction, AIGenerateStatus
from ai.ai_nexus import get_ai_nexus
from common.config.config import settings
from common.utils.generator import LZSDGenerator
from common.config.get_db import get_db_context
from core.entity.do.users_do import User
from dao.ai_log_dao import AILogDAO
from dao.ai_model_dao import AiModelDAO
from service.usage_service import UsageService
from service.content_audit_service import get_generated_content_audit_service


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
            origin_prompt: str,
            user_prompt: str,
            level: int,
            action_type: str,
            bid: str | None = None,
            temperature: float | None = None,
            max_tokens: int | None = None,
            tokenEstimate : int | None = 0,
            system_prompt: str | None = None,
            enable_web_search: bool = False,
            correlation=None,
            background_tasks=None,

    )->str:
        """
        第一阶段：校验、记录、生成请求ID (同步执行，快速返回)
        """
        user_id = user.pkId
        request_id = LZSDGenerator.generate_request_id()
        if correlation is None:
            correlation = []

        final_system_prompt = system_prompt or settings.ai_system_prompt
        final_temperature = temperature or settings.ai_temperature
        final_max_tokens = max_tokens or settings.ai_max_tokens

        usage_service = UsageService(self.db)

        input_user_prompt = user_prompt
        await usage_service.record(
            user_id=user_id,
            request_id=request_id,
            level=level,
            node_ids=correlation,
            bid=bid,
            origin_prompt=origin_prompt,
            system_prompt=final_system_prompt,
            user_prompt=input_user_prompt,
            temperature=final_temperature,
            output_content="",
            action_type=AIAction(action_type),

        )

        if background_tasks is not None:
            background_tasks.add_task(
                async_generate_task,
                request_id=request_id,
                ai_level=level,
                input_user_prompt=input_user_prompt,
                system_prompt=final_system_prompt,
                temperature=final_temperature,
                max_tokens=final_max_tokens,
                enable_web_search=enable_web_search,
            )

        return request_id


def _should_retry_with_level2(error: Exception) -> bool:
    """
    命中特定 Gemini 渠道/模型不可用错误时，降级到 level=2 重试
    """
    error_text = str(error)
    return (
        "Insufficient Balance" in error_text
    )

async def async_generate_task(
        request_id: str,
        ai_level:int,
        input_user_prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    enable_web_search: bool = False,
):
    """后台异步执行 AI 调用并更新结果"""
    nexus = get_ai_nexus()
    ai_provider = AIProvider.from_level(ai_level)
    # 构造待尝试的 provider 序列
    providers_to_try = [ai_provider]
    ai_rsp = None
    error_msg = ""

    for i, current_provider in enumerate(providers_to_try):
        try:
            logger.info(f"【{current_provider.name}】req:{request_id} 开始生成 提示词:{textwrap.shorten(input_user_prompt, width=20, placeholder="...")} temperature:{temperature} max_tokens:{max_tokens}")
            ai_rsp = await nexus.generate_novel_text(
                provider=current_provider,
                user_prompt=input_user_prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                enable_web_search=enable_web_search,
            )
            logger.info(f"【{current_provider.name}】req:{request_id} 生成结束 返回:{textwrap.shorten(ai_rsp.content, width=20, placeholder="...")}")
            break  # 成功则跳出循环
        except Exception as e:
            logger.info(f"【{current_provider.name}】req:{request_id} 生成异常 {e}")
            # 如果还有重试机会，且符合降级条件
            if i == 0 and ai_level > 0 and _should_retry_with_level2(e):
                fallback = AIProvider.from_level(2)
                providers_to_try.append(fallback)
                logger.warning(f"Req {request_id}: 命中特定错误，准备降级至 {fallback}")
                continue

            # 否则记录错误并彻底结束
            logger.error(f"Generate Error for {request_id}: {e}")
            error_msg = str(e)
            break

    if ai_rsp:
        async with get_db_context() as db:
            
            # audit_service = get_generated_content_audit_service()
            # try:
            #     audit_result = await audit_service.audit_generated_result(ai_rsp, use_semantic=True)
            #     if not audit_result.passed:
            #         logger.warning(f"RequestId: {request_id} 生成结果未通过审核：{audit_result.reason}")
            #         ai_rsp.content = f"{audit_result.reason}"
            # except Exception as exc:
            #     logger.warning(f"RequestId: {request_id} 生成结果审核失败，按原结果继续入库: {exc}")

            await UsageService(db).update_output_content_by_request_id(
            request_id=request_id,
            ai_rsp=ai_rsp,
            status=AIGenerateStatus.SUCCESS if ai_rsp else AIGenerateStatus.FAILED,
            error_msg=error_msg)

