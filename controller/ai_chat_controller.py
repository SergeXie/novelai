from typing import Optional

from fastapi import APIRouter, Depends, BackgroundTasks, Query, Body

from ai.adapters.enums import AIAction
from common.config.get_db import get_db
from common.response.response_util import ResponseUtil
from core.deps.auth import get_current_user, check_user_quota_or_raise
from core.entity.do.users_do import User
from service.ai_chat_service import AIChatService
from service.ai_service import AIService
from service.usage_service import UsageService

aiChatController = APIRouter(prefix="/ai/chat", tags=["AIChat"])

@aiChatController.get("/group/list")
async def get_groups(db= Depends(get_db), current_user: User = Depends(get_current_user)):
    data = await AIChatService.get_groups(db=db, current_user=current_user)
    return ResponseUtil.success(data={"list": data})

@aiChatController.get("/group/delete")
async def delete_group(
        gid: str = Query(0, description="组id"),
        db= Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    await AIChatService.delete_group(db=db, gid=gid, current_user=current_user)
    return ResponseUtil.success()


@aiChatController.post("/completions")
async def completions(
        background_tasks: BackgroundTasks,
        gid: Optional[str] = Body(None, embed=True),
        level: int = Body(..., embed=True),  # 建议 level 类型用 float
        content: str = Body(..., embed=True),  # content 通常保持必填
        db=Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    user_prompt = content
    if not user_prompt:
        return ResponseUtil.error(msg="聊天内容不能为空")

    await check_user_quota_or_raise(frozen_token_length=(len(user_prompt) + 3000), user_info=current_user)

    group_id = await AIChatService.completions(db=db, gid=gid, current_user=current_user, content=content)
    temperature = 0.7

    ai_srv = AIService(db=db)
    request_id = await ai_srv.prepare_and_record_request(
        user=current_user,
        bid=group_id,
        origin_prompt=user_prompt,
        user_prompt=user_prompt,
        system_prompt="你是一个陪聊",
        level=level,
        temperature=temperature,
        action_type=AIAction.Chat.value,
        background_tasks=background_tasks,
    )

    # 5. 立即返回 requestId 供前端轮询
    return ResponseUtil.success(data={"requestId": request_id, "groupId":group_id})


@aiChatController.get("/history", summary="分页获取对话记录")
async def get_history_list(
        gid: str = Query(..., description="组ID "),
        offsetId: int = Query(0, description="偏移"),
        size: int = Query(10, ge=1, le=500, description="每页数量"),
        user=Depends(get_current_user),
        db=Depends(get_db)
):
    service = UsageService(db=db)
    result = await service.get_chat_history(bid=gid, offset_id=offsetId, size=size, with_content=True)
    return ResponseUtil.success(data=result)
