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
from service.ai_service import AiModelService
from service.usage_service import UsageService

aiController = APIRouter()


@aiController.get("/engineList", name="模型列表")
async def list_models(
    db=Depends(get_db),
):
    """
    获取 AI 模型列表
    """
    models = await AiModelService.list_models(
        db,
    )
    # 显式走 Pydantic v2（你当前标准做法）
    resp = [AiModelResp.model_validate(m) for m in models]

    return ResponseUtil.success(data=resp)


@aiController.post("/generate", summary="根据设定生成小说片段")
async def generate(
        request: GenerateRequest,
        background_tasks: BackgroundTasks,
        db=Depends(get_db),
        user=Depends(get_login_user),
        nexus=Depends(get_ai_nexus),
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

    ai_provider = AIProvider.from_level(level)
    system_prompt, output_prompt = "", ""

    request_id = uuid.uuid4().hex

    # --- 第一阶段：快查并立即释放 ---
    # 使用 contextmanager 确保查完瞬间连接就回池子
    usage_service = UsageService(db=db)
    await usage_service.check_quota_or_raise(user_id=user.pkId, current_request_len=len(user_prompt))

    nodes_contents = await BookDAO.get_book_nodes_list(db, correlation, user.pkId)
    input_user_prompt = "\n".join(nodes_contents) + "\n" + user_prompt
    await usage_service.record(
        user_id=user.pkId,
        request_id=request_id,
        level=level,
        node_ids=correlation,
        bid=bid,
        origin_prompt=user_prompt,
        system_prompt=system_prompt,
        user_prompt=input_user_prompt,
        temperature=temperature,
        output_content=output_prompt,
    )

    # 4. 第二阶段：将耗时的 AI 生成丢入后台任务，不阻塞当前响应
    background_tasks.add_task(
        async_generate_task,  # 具体的执行函数
        nexus,
        ai_provider,
        input_user_prompt,
        request,
        request_id
    )

    # 5. 立即返回 requestId 供前端轮询
    return ResponseUtil.success(data={"requestId": request_id})

async def async_generate_task(nexus, ai_provider, input_user_prompt, request, request_id):
    """后台异步执行 AI 调用并更新结果"""
    system_prompt, output_prompt = "", ""
    try:
        # 真正的 AI 耗时操作
        system_prompt, output_prompt = await nexus.generate_novel_text(
            provider=ai_provider,
            user_prompt=input_user_prompt,
            temperature=request.temperature,
        )
        status = 1 # 成功
    except Exception as e:
        output_prompt = f"Error: {str(e)}"
        status = 0 # 失败
        logger.error(f"Async Generation Error for {request_id}: {output_prompt}")

    # 使用新的数据库上下文更新结果
    async with get_db_context() as db:
        usage_service = UsageService(db=db)
        await usage_service.update_output_content_by_request_id(request_id, output_prompt)


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

    service = AiModelService()

    await service.delete_history(
        db=db,
        uid=user.pkId,
        request_ids=req.requestIds
    )

    return ResponseUtil.success(msg="删除成功")