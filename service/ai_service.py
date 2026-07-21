import textwrap
from typing import Optional, Dict, Any, List

from fastapi import BackgroundTasks
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from ai.adapters.enums import AIProvider, AIAction, AIGenerateStatus
from ai.ai_nexus import get_ai_nexus
from common.config.config import settings
from common.config.get_db import get_db_context
from common.exception.errors import NotFoundError, ServerError
from common.exception.lzsd_exception import ServiceWarning
from common.modules.book_exporter import BookExporter
from common.utils.generator import LZSDGenerator
from core.deps.auth import check_user_quota_or_raise
from core.entity.do.books import Book
from core.entity.do.generate_log import AiNovelGenerateLog
from core.entity.do.users_do import User
from core.entity.vo.ai_response import AICompletionResponse
from core.enums.prompt_sys_var import PromptEngineType
from dao.ai_log_dao import AILogDAO
from dao.ai_model_dao import AiModelDAO
from dao.global_lexicon_dao import GlobalLexiconDAO
from dao.prompt_square_dao import PromptSquareDAO
from service.ai_prompt_service import PromptService
from service.book_service import BookService
from service.usage_service import UsageService


class AIService:

    def __init__(self, db: AsyncSession):
        self.db = db
        self.fill_context = []

    async def fill_context_with_adapter(self, data: list):
        self.fill_context = data or []

    @staticmethod
    def _snapshot_model_config(model) -> dict:
        return {
            "id": model.id,
            "level": model.level,
            "model_name": model.model_name,
            "model_identifier": model.model_identifier,
            "provider": model.provider,
            "multiplier": float(model.multiplier or 1),
            "max_tokens": int(model.max_tokens or 4096),
            "temperature": float(model.temperature or 0.7),
            "context_window": int(model.context_window or 32768),
            "base_url": model.base_url,
            "api_key": model.api_key,
            "weight": model.weight,
            "status": model.status,
        }

    async def get_model_config_by_level(self, level: int, *, only_enabled: bool = True) -> dict:
        model = await AiModelDAO(self.db).get_model_by_level(level)
        if not model or (only_enabled and model.status != 1):
            raise ServiceWarning(f"模型不可用 level={level}")
        return self._snapshot_model_config(model)

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
        实时获取模型列表，确保 /engineList 返回数据库最新配置。
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
            template_key: str | None = None,
            background_tasks=None,
    ) -> tuple[str, None] | tuple[str, AICompletionResponse | None]:
        await check_user_quota_or_raise(frozen_token_length=tokenEstimate, user_info=user, level=level)
        """
        第一阶段：校验、记录、生成请求ID
        当 background_tasks 为 None 时，直接同步等待任务完成。
        """
        user_id = user.pkId
        request_id = LZSDGenerator.generate_request_id()
        if correlation is None:
            correlation = []

        model_config = await self.get_model_config_by_level(level)

        final_system_prompt = system_prompt or settings.ai_system_prompt
        final_temperature = temperature if temperature is not None else model_config["temperature"]
        model_max_tokens = model_config["max_tokens"]
        final_max_tokens = max_tokens  # 不传入时为 None，由适配器决定默认值

        # 字数提示注入（入库前），确保数据库中保存的 prompt 包含字数要求
        if final_max_tokens:
            range_offset = 300 if final_max_tokens >= 2000 else 200
            min_tokens = final_max_tokens - range_offset
            max_tokens_range = final_max_tokens + range_offset
            user_prompt = f"{user_prompt}\n\n【字数建议：{min_tokens}~{max_tokens_range}字】\n请尽量将篇幅控制在以上范围内，以保证内容的完整性与质量。"

        usage_service = UsageService(self.db)

        input_user_prompt = user_prompt

        # ================================
        # 检查本地模型时间限制
        # ================================
        output_content = ""

        # ================================
        # 正常记录日志
        # ================================
        log = await usage_service.record(
            user_id=user_id,
            request_id=request_id,
            level=level,
            node_ids=correlation,
            template_key=template_key,
            bid=bid or "",
            origin_prompt=origin_prompt,
            system_prompt=final_system_prompt,
            user_prompt=input_user_prompt,
            temperature=final_temperature,
            output_content=output_content,
            action_type=AIAction(action_type),
            max_tokens=final_max_tokens,
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
            "model_config": model_config,
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

    async def execute(
            self,
            db: AsyncSession,
            user: User,
            action_type: AIAction,
            level: int,
            temperature:  Optional[float] = None,
            max_tokens: Optional[int] = None,
            template_key: Optional[str] = None,
            inputs: Optional[Dict[str, Any]] = None,
            bid: Optional[str] = None,
            user_prompt: str = None,
            correlation: Optional[List[Any]] = None,
            lexicon_ids: Optional[List[int]] = None,
            background_tasks: Optional[BackgroundTasks] = None
    ) -> str:
        """
        智能解析提示词组件，拼装上下文，估算冻结Token并记录AI调用流水
        """
        # 1. 基础 Token 估算：用户原始 prompt + 基础消耗通道 (中文字符 Token 转换率通常按 1.5 到 2 估算)
        user_prompt_len = len(user_prompt) if user_prompt else 0
        frozen_tokens = int(user_prompt_len * 1.5) + 3000

        # 构建用户可见的审计追溯链条（利用列表优雅组装，避免频繁的字符串 += 导致内存损耗）
        origin_prompt_parts = []
        template_prompt = ""
        final_inputs = inputs or {}

        # 实例化相关业务域 Service（收拢到顶部，复用同一个 db 实例）
        book_service = BookService(db)
        prompt_service = PromptService(db)

        book : Optional[Book] = None
        if bid:
            book = await book_service.get_book_by_bid(bid=bid, user_id=user.pkId)
            if not book:
                raise NotFoundError(msg=f"作品[{bid}]不存在")

        # 2. 解析与渲染提示词模板域
        if template_key:
            tpl = await PromptSquareDAO.get_template_by_key(db, template_key)
            if not tpl or tpl.status == 0:
                raise NotFoundError(msg="提示词模版不存在或已下架")

            origin_prompt_parts.append(f"【模版】{tpl.title}")
            frozen_tokens += (tpl.freeze_tokens or 0)

            # 如果关联了书籍且含有系统内置插槽，自动进行书籍知识库 Markdown 导出
            if bid and "sys_book_info" in final_inputs:
                nodes = await book_service.get_basic_nodes(bid=bid, user_id=user.pkId) or []
                leaf_ids = [node.id for node in nodes]

                exporter = BookExporter(db)
                final_inputs["sys_book_info"] = await exporter.export_to_markdown(book=book, leaf_node_ids=leaf_ids)

            # 执行 Jinja2 或其他引擎的动态渲染
            try:
                template_prompt = await PromptService.render_prompt_with_params(
                    prompt=tpl.content,
                    inputs=final_inputs,
                    engine_type=PromptEngineType.from_str(tpl.engine_type)
                )
                # 渲染后的长文本 Token 损耗追加
                frozen_tokens += int(len(template_prompt) * 1.5)
            except Exception as e:
                raise ServerError(msg=f"提示词模板[{tpl.title}]渲染异常: {e}")

        # 3. 解析动态关联的上下文节点（如：勾选的角色、大纲片段）
        book_context_prompt = ""
        if bid and book:
            book_context_prompt = "# 小说核心设定\n" + await prompt_service.generate_book_base_prompt(book=book)
            if correlation:
                book_context_prompt += "\n" +  await prompt_service.generate_prompt_by_nodes(
                    user_id=user.pkId,
                    bid=bid,
                    ids=correlation,
                )

        # 词条是独立上下文，不参与书籍节点查询；仅允许使用自己的或全平台公开的词条。
        lexicon_context_prompt = ""
        lexicon_correlation = []
        if lexicon_ids:
            unique_lexicon_ids = list(dict.fromkeys(lexicon_ids))
            lexicons = await GlobalLexiconDAO.get_visible_lexicons(
                db=db,
                lexicon_ids=unique_lexicon_ids,
                user_id=user.pkId,
            )
            if len(lexicons) != len(unique_lexicon_ids):
                raise ServiceWarning("存在无效或无权限查看的词条")

            lexicon_parts = [
                f"{item.title}\n{item.content or ''}".rstrip()
                for item in lexicons
            ]
            lexicon_context_prompt = "\n# 公共词条\n" + "\n\n".join(lexicon_parts)
            lexicon_correlation = [item.id for item in lexicons]
            frozen_tokens += int(len(lexicon_context_prompt) * 1.5)

        # 4. 最终核心全文本组装（清洗空文本段落，按换行合并）
        final_user_prompt = "\n".join(filter(None, [book_context_prompt, lexicon_context_prompt, template_prompt, user_prompt]))
        # 5. 组装最终追溯用的标记
        if user_prompt:
            origin_prompt_parts.append(f"【提示词】{user_prompt}")
        origin_prompt = " ".join(origin_prompt_parts)

        log_correlation = list(correlation) if correlation is not None else []
        log_correlation.extend(lexicon_correlation)
        print("log_correlation:{}".format(log_correlation))
        # 6. 持久化请求日志并激活异步任务网关
        request_id, _ = await self.prepare_and_record_request(
            user=user,
            bid=bid,
            origin_prompt=origin_prompt,
            user_prompt=final_user_prompt,
            level=level,
            action_type=action_type,
            temperature=temperature or 0.7,
            correlation=log_correlation,
            template_key=template_key,
            max_tokens=max_tokens,
            tokenEstimate=frozen_tokens,
            background_tasks=background_tasks
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
        ai_level: int,
        input_user_prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
        context: list,
        log: AiNovelGenerateLog,
        enable_web_search: bool = False,
        model_config: dict | None = None,
) -> AICompletionResponse | None:
    """后台异步执行 AI 调用并更新结果"""
    nexus = get_ai_nexus()
    ai_provider = AIProvider.parse(value=ai_level)
    # 构造待尝试的 provider 序列
    providers_to_try = [ai_provider]
    provider_model_configs = {ai_provider: model_config}
    ai_rsp = None
    error_msg = ""

    # 假如是拆书 可以复用
    if await reuse_book_destructor_data(log=log):
        return None

    for i, current_provider in enumerate(providers_to_try):
        try:
            current_model_config = provider_model_configs.get(current_provider)
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
                model_config=current_model_config,
            )
            logger.info(
                f"【{current_provider.name}】req:{request_id} 生成结束 返回:{textwrap.shorten(ai_rsp.content, width=20, placeholder="...")}")
            break  # 成功则跳出循环
        except Exception as e:
            logger.info(f"【{current_provider.name}】req:{request_id} 生成异常 {e}")
            # 如果还有重试机会，且符合降级条件
            if i == 0 and ai_level > 0 and _should_retry_with_level2(e):
                fallback = AIProvider.DOUBAO
                if fallback not in provider_model_configs:
                    async with get_db_context() as db:
                        provider_model_configs[fallback] = await AIService(db).get_model_config_by_level(fallback.value)
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
