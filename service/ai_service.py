import datetime
import textwrap

from loguru import logger
from sqlalchemy import false
from sqlalchemy.ext.asyncio import AsyncSession

from ai.adapters.enums import AIProvider, AIAction, AIGenerateStatus
from ai.ai_nexus import get_ai_nexus
from common.config.config import settings
from common.utils.generator import LZSDGenerator
from common.config.get_db import get_db_context
from core.entity.do.generate_log import AiNovelGenerateLog
from core.entity.do.users_do import User
from core.entity.vo.ai_response import AICompletionResponse
from dao.ai_log_dao import AILogDAO
from dao.ai_model_dao import AiModelDAO
from service.usage_service import UsageService
from service.content_audit_service import get_generated_content_audit_service


class AIService:

    def __init__(self, db: AsyncSession):
        self.db = db
        self.fill_context = []

    async def fill_context_with_adapter(self, data: list):
        self.fill_context = data or []

    async def build_chat_context_messages(
            self,
            bid: str,
            user_id: int,
            offset_id: int = 0,
            size: int = 10,
    ) -> list[dict]:
        logs, _ = await AILogDAO(self.db).get_full_logs_by_offset(
            user_id=user_id,
            bid=bid,
            offset_id=offset_id,
            size=size,
        )

        messages = []
        for log in reversed(logs):
            user_prompt = (getattr(log, "userPrompt", None) or "").strip()
            output_content = (getattr(log, "outputContent", None) or "").strip()

            if not user_prompt or not output_content:
                continue

            messages.append({"role": "user", "content": user_prompt})
            messages.append({"role": "assistant", "content": output_content})

        return messages

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
            action_type: AIAction,
            bid: str | None = None,
            temperature: float | None = None,
            max_tokens: int | None = None,
            tokenEstimate: int | None = 0,
            system_prompt: str | None = None,
            enable_web_search: bool = False,
            correlation=None,
            background_tasks=None,
    ) -> tuple[str, None] | tuple[str, AICompletionResponse | None]:
        """
        第一阶段：校验、记录、生成请求ID
        当 background_tasks 为 None 时，直接同步等待任务完成。
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

        # ================================
        # 检查本地模型时间限制
        # ================================
        output_content = ""
        if level == 0:  # 本地部署模型
            now = datetime.datetime.now()
            weekday = now.weekday()  # 0=周一, 6=周日
            # 工作日限制：周一到周五 09:00~19:00
            if weekday < 7:
                start_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
                end_time = now.replace(hour=19, minute=0, second=0, microsecond=0)
                if start_time <= now <= end_time:
                    output_content = "当前访问人数过多，疯狂加服务器中，请切换模型或者稍后再试。"
                    logger.info(output_content)
                    # 限制时间直接返回 None
                    # 记录日志时也保存 output_content
                    log = await usage_service.record(
                        user_id=user_id,
                        request_id=request_id,
                        level=level,
                        node_ids=correlation,
                        bid=bid,
                        status=AIGenerateStatus.SUCCESS,
                        origin_prompt=origin_prompt,
                        system_prompt=final_system_prompt,
                        user_prompt=input_user_prompt,
                        temperature=final_temperature,
                        output_content=output_content,
                        action_type=AIAction(action_type),
                    )
                    return request_id, None

        # ================================
        # 正常记录日志
        # ================================
        log = await usage_service.record(
            user_id=user_id,
            request_id=request_id,
            level=level,
            node_ids=correlation,
            bid=bid,
            origin_prompt=origin_prompt,
            system_prompt=final_system_prompt,
            user_prompt=input_user_prompt,
            temperature=final_temperature,
            output_content=output_content,
            action_type=AIAction(action_type),
        )

        # ================================
        # 任务分发逻辑
        # ================================
        task_kwargs = {
            "request_id": request_id,
            "ai_level": level,
            "input_user_prompt": input_user_prompt,
            "system_prompt": final_system_prompt,
            "temperature": final_temperature,
            "max_tokens": final_max_tokens,
            "enable_web_search": enable_web_search,
            "log": log,
            "context": self.fill_context,
        }

        if background_tasks is not None:
            # 异步模式：交给 FastAPI 后台任务
            background_tasks.add_task(async_generate_task, **task_kwargs)
            logger.info(f"任务 {request_id} 已加入后台队列")
            return request_id, None
        else:
            # 同步模式：阻塞等待 AI 执行完成
            logger.info(f"任务 {request_id} 正在同步执行...")
            ai_rsp = await async_generate_task(**task_kwargs)
            return request_id, ai_rsp


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
        ai_level: int,
        input_user_prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
        context: list,
        log: AiNovelGenerateLog,
        enable_web_search: bool = False,
) -> AICompletionResponse | None:
    """后台异步执行 AI 调用并更新结果"""
    nexus = get_ai_nexus()
    ai_provider = AIProvider.parse(value=ai_level)
    # 构造待尝试的 provider 序列
    providers_to_try = [ai_provider]
    ai_rsp = None
    error_msg = ""

    # 假如是拆书 可以复用
    if await reuse_book_destructor_data(log=log):
        return None

    for i, current_provider in enumerate(providers_to_try):
        try:
            logger.info(
                f"[{current_provider.name}] req:{request_id} 开始生成 提示词:{textwrap.shorten(input_user_prompt, width=32, placeholder="...")} temperature:{temperature} max_tokens:{max_tokens}")
            normalized_context = await nexus.fill_context_with_adapter(
                provider=current_provider,
                data=context
            )  # 如果需要对提示词进行特殊处理，可以在这里实现

            ai_rsp = await nexus.generate_novel_text(
                provider=current_provider,
                user_prompt=input_user_prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                context_messages=normalized_context,
                enable_web_search=enable_web_search,
            )
            logger.info(
                f"【{current_provider.name}】req:{request_id} 生成结束 返回:{textwrap.shorten(ai_rsp.content, width=20, placeholder="...")}")
            break  # 成功则跳出循环
        except Exception as e:
            logger.info(f"【{current_provider.name}】req:{request_id} 生成异常 {e}")
            # 如果还有重试机会，且符合降级条件
            if i == 0 and ai_level > 0 and _should_retry_with_level2(e):
                fallback = AIProvider.DOUBAO
                providers_to_try.append(fallback)
                logger.warning(f"Req {request_id}: 命中特定错误，准备降级至 {fallback}")
                continue

            # 否则记录错误并彻底结束
            logger.error(f"Generate Error for {request_id}: {e}")
            error_msg = str(e)
            break

    if ai_rsp or error_msg:
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

    return ai_rsp

async def reuse_book_destructor_data(
        log: AiNovelGenerateLog,
) -> bool:
    if log.actionType == AIAction.Deconstruct:
        sha256_id = log.bid
        async with get_db_context() as db:
            dao = AILogDAO(db=db)
            reuse_log = await dao.get_invalid_book_destructor_log(bid=sha256_id)
            if log and reuse_log:
                await dao.sync_ai_log_data(source_request_id=reuse_log.requestId, target_request_id=log.requestId)
                logger.info(f"[拆书]{sha256_id} 复用成功{reuse_log.requestId}--->{log.requestId}")
                return True

    return False
