from fastapi import APIRouter, Depends, BackgroundTasks, Query, Header

from ai.adapters.enums import AIAction
from common.config.config import settings
from common.config.get_db import get_db
from common.exception.errors import NotFoundError
from common.response.response_util import ResponseUtil
from core.deps.auth import get_current_user, check_book_owner, check_user_quota_or_raise
from core.entity.req.ai_execute_req import AIExecuteReq
from core.entity.schemas import GenerateRequest
from core.entity.vo.ai_model_vo import AiModelResp, DeleteHistoryReq
from dao.ai_model_dao import AiModelDAO
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


@aiController.post("/engineList/refresh", name="刷新AI模型配置缓存")
async def refresh_model_config_cache(
        db=Depends(get_db)
):
    """
    重新加载 mc_ai_models 到内存缓存，让数据库中的模型配置变更无需重启即可生效。
    """
    await AiModelDAO(db).refresh_models_cache()
    return ResponseUtil.success(data={}, msg="模型配置缓存刷新成功")


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


@aiController.get("/ai/log/list")
async def get_log_list(
        page: int = Query(1, ge=1, description="页码"),
        pageSize: int = Query(20, ge=1, le=50, description="每页数量"),
        startTime: str | None = Query(None, description="起始时间"),
        endTime: str | None = Query(None, description="结束时间"),
        originPrompt: str | None = Query(None, description="提示词关键字"),
        actionType: str | None = Query(None, description="行为类型"),
        user=Depends(get_current_user),
        db=Depends(get_db)
):
    service = UsageService(db=db)
    result = await service.get_logs_page(
        user_id=user.pkId,
        page=page,
        pageSize=pageSize,
        start_time=startTime,
        end_time=endTime,
        origin_prompt=originPrompt,
        action_type=actionType,
    )
    return ResponseUtil.success(data=result)


@aiController.get("/ai/log/detail")
async def get_log_detail(requestId: str, db=Depends(get_db), _=Depends(get_current_user)):
    service = UsageService(db=db)
    rsp = await service.get_log_detail(request_id=requestId)
    if rsp is None:
        return NotFoundError

    return ResponseUtil.success(data=rsp)


@aiController.post("/generate", summary="根据设定生成小说片段")
async def generate(
        req: GenerateRequest,
        background_tasks: BackgroundTasks,
        db=Depends(get_db),
        user=Depends(get_current_user),
):
    """
    根据设定生成小说片段（输入 / 输出全量留痕）
    """


    if req.bid:
        await check_book_owner(bid=req.bid, db=db, user=user)

    user_prompt = req.user_prompt
    if not user_prompt or not user_prompt.strip():
        raise ResponseUtil.error(msg="自定义提示词内容不能为空")

    ai_service = AIService(db=db)
    request_id = await ai_service.execute(db=db, user=user, action_type=AIAction.Generate, level=req.level,
                                          temperature=req.temperature,
                                          max_tokens=req.max_tokens, bid=req.bid, user_prompt=req.user_prompt,
                                          background_tasks=background_tasks)

    # 5. 立即返回 requestId 供前端轮询
    return ResponseUtil.success(data={"requestId": request_id})
