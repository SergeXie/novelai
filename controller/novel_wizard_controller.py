import json
from typing import Any

from fastapi import APIRouter, Depends

from ai.adapters.enums import AIAction
from ai.ai_nexus import ai_clean_json
from common.config.get_db import get_db
from common.response.response_util import ResponseUtil
from common.utils.generator import LZSDGenerator
from core.deps.auth import get_current_user, check_user_quota_or_raise
from core.entity.do.users_do import User
from core.entity.schemas import NovelWizardStepRequest
from service.ai_service import AIService

# 小说向导相关路由
novelWizardController = APIRouter(prefix="/ai/chat", tags=["NovelWizard"])

# 小说向导步骤配置：
# - step: 向导步骤编号
# - name: 前端展示名称
# - key: 该步骤结果写入 context 时使用的字段名
# - system_prompt: 约束模型角色与输出格式
# - prompt: 实际发送给模型的用户提示词模板
NOVEL_WIZARD_STEPS: dict[int, dict[str, Any]] = {
    1: {
        "name": "灵感启迪",
        "key": "book_seed",
        "system_prompt": "你是中文网络小说策划编辑，只输出结构化 JSON，不要解释。",
        "prompt": (
            "根据下面的脑洞，为中文网文生成标题、剧情简介。\n"
            "脑洞：{idea}\n"
            "请严格输出 JSON，字段包括 title、hook、synopsis。"
        ),
    },
    2: {
        "name": "角色塑形",
        "key": "book_people",
        "system_prompt": "你是角色设定师，只输出结构化 JSON，不要解释。",
        "prompt": (
            "根据下面的脑洞和前序内容，生成 3-5 个核心角色。\n"
            "脑洞：{idea}\n"
            "前序内容：\n{context_json}\n"
            "请严格输出 JSON，字段 characters，数组内每个角色包含 name、role、personality、background、goal、conflict。"
        ),
    },
    3: {
        "name": "世界构筑",
        "key": "book_world",
        "system_prompt": "你是世界观架构师，只输出结构化 JSON，不要解释。",
        "prompt": (
            "根据下面的脑洞、角色和前序内容，生成适配故事的世界观设定。\n"
            "脑洞：{idea}\n"
            "前序内容：\n{context_json}\n"
            "请严格输出 JSON，字段 world，至少包含 era、background、core_rules、major_forces、conflicts。"
        ),
    },
    4: {
        "name": "创作准则",
        "key": "book_style",
        "system_prompt": "你是小说编辑，只输出结构化 JSON，不要解释。",
        "prompt": (
            "根据下面的脑洞、角色、世界观和前序内容，生成写作要求与基调。\n"
            "脑洞：{idea}\n"
            "前序内容：\n{context_json}\n"
            "请严格输出 JSON，字段 style，至少包含 language_style、pov、pacing、taboo、recommended_length。"
        ),
    },
    5: {
        "name": "结构大纲",
        "key": "book_outline",
        "system_prompt": "你是剧情策划，只输出结构化 JSON，不要解释。",
        "prompt": (
            "根据下面的脑洞、角色、世界观和写作准则，生成故事大纲。\n"
            "脑洞：{idea}\n"
            "前序内容：\n{context_json}\n"
            "请严格输出 JSON，字段 outline，至少包含 theme、main_line、story_arcs。"
        ),
    },
    6: {
        "name": "章节细化",
        "key": "book_chapters",
        "system_prompt": "你是章节规划师，只输出结构化 JSON，不要解释。",
        "prompt": (
            "根据下面的脑洞、前序内容和章节数，生成细化章节列表。\n"
            "脑洞：{idea}\n"
            "章节数：{chapter_count}\n"
            "前序内容：\n{context_json}\n"
            "请严格输出 JSON，字段 chapters，数组内每章包含 chapter、title、summary、key_event。"
        ),
    },
}


def _get_wizard_step_config(step: int) -> dict[str, Any] | None:
    """根据步骤编号获取向导配置，不存在时返回 None。"""
    return NOVEL_WIZARD_STEPS.get(step)


def _build_wizard_prompt(request: NovelWizardStepRequest, context_json: str) -> tuple[dict[str, Any], str]:
    """
    根据当前请求和上下文，构造本次调用 AI 的 prompt。

    返回：
    - 当前步骤配置
    - 渲染后的用户提示词
    """
    config = _get_wizard_step_config(request.step)
    if not config:
        raise ValueError("不支持的向导步骤")

    prompt = config["prompt"].format(
        idea=request.idea.strip(),
        context_json=context_json,
        chapter_count=request.chapter_count,
    )
    return config, prompt


def _normalize_wizard_context(context: dict[str, Any] | str) -> tuple[str, dict[str, Any]]:
    """
    统一处理前端传入的 context。

    支持两种输入：
    1. dict：直接作为上下文对象
    2. str：尝试按 JSON 解析，解析失败则按原始文本处理

    返回：
    - 适合放入 prompt 的字符串形式 context_json
    - 可继续累积写入步骤结果的 dict 形式 merged_context
    """
    if isinstance(context, dict):
        return json.dumps(context, ensure_ascii=False, indent=2), dict(context)

    text = (context or "").strip()
    if not text:
        return "{}", {}

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # 非 JSON 文本时，保留原文，便于继续传递上下文
        return text, {"raw_context": text}

    if isinstance(parsed, dict):
        return json.dumps(parsed, ensure_ascii=False, indent=2), dict(parsed)

    # JSON 能解析但不是对象时，统一包一层 raw_context，避免后续上下文写入异常
    return json.dumps(parsed, ensure_ascii=False, indent=2), {"raw_context": parsed}


@novelWizardController.post("/novelstep", summary="小说向导单步生成")
async def novel_wizard_step(
        request: NovelWizardStepRequest,
        db=Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """
    小说向导单步生成接口。

    处理流程：
    1. 校验脑洞参数
    2. 标准化前端传入的上下文
    3. 按步骤构建 prompt
    4. 校验用户额度
    5. 调用 AIService 发起请求并记录日志
    6. 尝试清洗 AI 返回内容为 JSON
    7. 将当前步骤结果合并进 context 并返回
    """
    # 脑洞是所有步骤的核心输入，不能为空
    if not request.idea or not request.idea.strip():
        return ResponseUtil.failure(msg="脑洞不能为空")

    try:
        # 将上下文统一转为 prompt 可读字符串 + 内部可写入字典
        context_json, merged_context = _normalize_wizard_context(request.context)
        step_config, user_prompt = _build_wizard_prompt(
            request=request,
            context_json=context_json,
        )
    except ValueError as exc:
        return ResponseUtil.failure(msg=str(exc))

    # 预检查用户配额，避免在额度不足时继续调用模型
    # 这里额外预留约 3000 token 作为响应空间
    await check_user_quota_or_raise(
        frozen_token_length=(len(user_prompt) + 3000),
        user_info=current_user,
        level=request.level,
    )

    # 若前端没有传 wizardId，则自动生成一个，便于同一向导会话串联多步结果
    wizard_id = request.wizardId or LZSDGenerator.generate_chat_group_id()
    ai_srv = AIService(db=db)

    # 准备并记录 AI 请求，统一走服务层
    request_id, ai_rsp = await ai_srv.prepare_and_record_request(
        user=current_user,
        bid=wizard_id,
        origin_prompt=request.idea,
        user_prompt=user_prompt,
        system_prompt=step_config["system_prompt"],
        level=request.level,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        action_type=AIAction.WorkFlow,
        tokenEstimate=len(user_prompt),
        correlation=[f"novel_wizard_step_{request.step}"],
        background_tasks=None,
    )

    # AI 返回为空时，直接视为失败
    if ai_rsp is None:
        return ResponseUtil.error(msg="AI 生成失败，请稍后重试")

    content = ai_rsp.content or ""
    try:
        # 尝试从模型输出中提取标准 JSON
        parsed_content = ai_clean_json(content)
    except Exception:
        # 如果清洗失败，则保留原始文本，避免接口整体报错
        parsed_content = None

    # 将当前步骤结果写入上下文，供下一步继续使用
    merged_context[step_config["key"]] = parsed_content if parsed_content is not None else content
    merged_context["wizardId"] = wizard_id

    return ResponseUtil.success(data={
        "wizardId": wizard_id,
        "requestId": request_id,
        "step": request.step,
        "stepName": step_config["name"],
        # content 保留原始模型输出，便于前端展示或排查问题
        "content": content,
        # parsedContent 为结构化结果，便于前端直接消费
        "parsedContent": parsed_content,
        # context 为合并后的上下文，可直接传给下一步
        "context": merged_context,
    })