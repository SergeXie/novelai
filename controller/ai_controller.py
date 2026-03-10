import uuid
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from loguru import logger
from starlette.status import HTTP_400_BAD_REQUEST

from ai.adapters.enums import AIProvider
from ai.ai_nexus import get_ai_nexus
from common.config.get_db import get_db, get_db_context
from common.response.response_util import ResponseUtil
from core.deps.auth import get_login_user
from core.entity.vo.ai_model_vo import AiModelResp, DeleteHistoryReq
from dao.book_dao import BookDAO
from core.entity.schemas import GenerateRequest
from service.ai_service import AIService, async_generate_task
from service.usage_service import UsageService

aiController = APIRouter()


@aiController.get("/engineList", name="模型列表")
async def list_models(
    db=Depends(get_db),
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
        user=Depends(get_login_user)
):
    """
    根据设定生成小说片段（输入 / 输出全量留痕）
    """
    user_prompt = request.user_prompt
    correlation = request.correlation
    bid = request.bid
    level = request.level
    temperature = request.temperature

    if not user_prompt:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="提示词不能为空")

    nodes_contents = await BookDAO.get_book_nodes_list(db, correlation, user.pkId)
    input_user_prompt = "\n".join(nodes_contents) + "\n" + user_prompt

    ai_service = AIService(db=db)
    request_id = await ai_service.prepare_and_record_request(
        user_id=user.pkId,
        bid=bid,
        origin_prompt=user_prompt,
        user_prompt=input_user_prompt,
        level=level,
        temperature=0.7,
        action_type="generate",
        correlation=correlation,
        background_tasks=background_tasks,
    )

    # 5. 立即返回 requestId 供前端轮询
    return ResponseUtil.success(data={"requestId": request_id})

@aiController.get("/poll")
async def poll(requestId: str, db=Depends(get_db), user=Depends(get_login_user)):
    usage_service = UsageService(db=db)
    output = await usage_service.poll_content_by_request_id(request_id=requestId)
    if output is None:
        output = ""
    return ResponseUtil.success(data=output)


@aiController.get("/history/list", summary="分页获取小说生成对话记录")
async def get_history_list(
        bid: str = Query(..., description="小说ID "),
        page: int = Query(1, ge=1, description="页码"),
        size: int = Query(10, ge=1, le=50, description="每页数量"),
        user=Depends(get_login_user),
        db=Depends(get_db)
):
    """
    根据 bid 获取历史生成的提示词列表（不含大文本结果）
    """
    # 简单的权限校验（可选：校验该 bid 是否属于该 user）
    # ...

    service = UsageService(db=db)
    result = await service.get_book_chat_history(bid, page, size)

    return ResponseUtil.success(data=result)


@aiController.post("/history/delete", name="小说生成对话记录删除")
async def delete_history(
    req: DeleteHistoryReq,
    user=Depends(get_login_user),
    db=Depends(get_db),
):

    service = AIService(db=db)

    await service.delete_history(
        uid=user.pkId,
        request_ids=req.requestIds
    )

    return ResponseUtil.success(msg="删除成功")