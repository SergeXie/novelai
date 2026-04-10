from fastapi import APIRouter, Depends, BackgroundTasks, Query

from ai.adapters.enums import AIAction
from common.config.config import settings
from common.config.get_db import get_db
from common.exception.lzsd_exception import InsufficientTokenException
from common.response.response_util import ResponseUtil
from core.deps.auth import get_current_user, check_book_owner, check_user_quota_or_raise
from core.entity.vo.ai_model_vo import AiModelResp, DeleteHistoryReq
from core.entity.schemas import GenerateRequest
from service.ai_prompt_service import PromptService
from service.ai_service import AIService
from service.usage_service import UsageService

aiController = APIRouter()


@aiController.get("/engineList", name="模型列表")
async def list_models(
    db=Depends(get_db),
    _=Depends(get_current_user)
):
    """
    获取 AI 模型列表
    """
    service = AIService(db=db)
    models = await service.list_models()
    # 显式走 Pydantic v2（你当前标准做法）
    resp = [AiModelResp.model_validate(m) for m in models]

    return ResponseUtil.success(data=resp)


@aiController.post("/generate", summary="根据设定生成小说片段")
async def generate(
        request: GenerateRequest,
        background_tasks: BackgroundTasks,
        db=Depends(get_db),
        user=Depends(get_current_user),
):
    """
    根据设定生成小说片段（输入 / 输出全量留痕）
    """
    await check_book_owner(bid=request.bid, db=db, user=user)

    user_prompt = request.user_prompt
    if not user_prompt:
        return ResponseUtil.error(msg="提示词不能为空")

    await check_user_quota_or_raise(frozen_token_length=(len(user_prompt) + 3000), user_info=user)

    correlation = request.correlation  # 章节ID
    bid = request.bid
    level = request.level
    temperature = request.temperature or 0.7

    prompt_service = PromptService(db=db)
    # 用于拼接书籍的基本信息（书名、简介、章节）
    final_prompt = await prompt_service.generate_prompt_by_nodes(user_id=user.pkId, bid=bid, ids=correlation)
    ai_service = AIService(db=db)

    combined_user_prompt = f"{final_prompt}\n{user_prompt}"
    
    request_id = await ai_service.prepare_and_record_request(
        user=user,
        bid=bid,
        origin_prompt=user_prompt,
        user_prompt=combined_user_prompt,
        level=level,
        temperature=temperature,
        action_type=AIAction.Generate.value,
        correlation=correlation,
        background_tasks=background_tasks,
    )

    # 5. 立即返回 requestId 供前端轮询
    return ResponseUtil.success(data={"requestId": request_id})


@aiController.get("/poll")
async def poll(requestId: str, db=Depends(get_db), user=Depends(get_current_user)):
    usage_service = UsageService(db=db)
    output = await usage_service.poll_content_by_request_id(request_id=requestId, user_id=user.pkId)
    if output is None:
        output = ""
    return ResponseUtil.success(data=output)


@aiController.get("/history/list", summary="分页获取小说生成对话记录")
async def get_history_list(
        bid: str = Query(..., description="小说ID "),
        page: int = Query(1, ge=1, description="页码"),
        size: int = Query(10, ge=1, le=50, description="每页数量"),
        user=Depends(get_current_user),
        db=Depends(get_db)
):
    """
    根据 bid 获取历史生成的提示词列表（不含大文本结果）
    """
    # 简单的权限校验（可选：校验该 bid 是否属于该 user）
    # ...

    await check_book_owner(bid=bid, db=db, user=user)

    service = UsageService(db=db)
    result = await service.get_book_chat_history(bid, page, size)

    return ResponseUtil.success(data=result)


@aiController.post("/history/delete", name="小说生成对话记录删除")
async def delete_history(
        req: DeleteHistoryReq,
        db=Depends(get_db),
        user=Depends(get_current_user),
):

    service = AIService(db=db)

    await service.delete_history(
        uid=user.pkId,
        request_ids=req.requestIds
    )

    return ResponseUtil.success(msg="删除成功")