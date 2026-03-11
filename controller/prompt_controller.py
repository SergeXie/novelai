from fastapi import APIRouter, Depends, Body, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from common.config.get_db import get_db
from common.response.response_util import ResponseUtil
from core.deps.auth import get_login_user
from core.entity.vo.prompt_register_vo import PromptRegistryResp
from service.ai_prompt_service import PromptService
from service.ai_service import AIService

promptController = APIRouter(prefix="/prompts", tags=["提示词管理"])

@promptController.get("/list", name="获取所有提示词模板")
async def list_all_prompts(db: AsyncSession = Depends(get_db), user=Depends(get_login_user)):
    # 实例化 Service 并透传 Session
    service = PromptService(db)

    # 调用 Service 业务
    data = await service.get_all_prompts()

    # 转换为 Schema 并返回
    result = [PromptRegistryResp.model_validate(p) for p in data]
    return ResponseUtil.success(data=result)


@promptController.post("/render", name="渲染提示词")
async def render(
        background_tasks: BackgroundTasks,
        bid: str = Body(...),
        level:int = Body(...),
        tool_key: str = Body(...),
        inputs: dict = Body(...),
        db: AsyncSession = Depends(get_db),
        user=Depends(get_login_user),

):
    service = PromptService(db)
    try:
        final_prompt = await service.render_prompt_content(tool_key, inputs)
        ai_service = AIService(db)
        payload = {
            "tool_key": tool_key,
            **inputs
        }
        request_id = await ai_service.prepare_and_record_request(
            user_id=user.pkId,
            bid=bid,
            user_prompt=final_prompt,
            level=level,
            temperature=0.7,
            action_type="render",
            correlation=payload,
            background_tasks=background_tasks,
        )
        return ResponseUtil.success(data={"request_id": request_id})
    except ValueError as e:
        return ResponseUtil.error(msg=str(e))