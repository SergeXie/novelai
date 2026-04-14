from typing import Optional

from fastapi import APIRouter, Depends, Body, BackgroundTasks

from common.config.get_db import get_db
from common.response.response_util import ResponseUtil
from core.deps.auth import get_current_user
from service.prompt_square_service import PromptSquareService

aiTemplateController = APIRouter(prefix="/ai/template")


@aiTemplateController.post("/execute")
async def execute(
        background_tasks: BackgroundTasks,
        templateKey: str = Body(...),
        level: int = Body(...),
        userPrompt: str = Body(...),
        bid: str = Body(...),
        inputs: Optional[dict] = Body(None),
        template: Optional[float] = Body(None),
        maxTokens: Optional[int] = Body(None),
        user=Depends(get_current_user),
        db=Depends(get_db), ):
    request_id = await PromptSquareService.execute_by_template(
        db=db,
        level=level,
        template_key=templateKey,
        user_prompt=userPrompt,
        user=user,
        bid=bid,
        inputs=inputs,
        temperature=template,
        max_tokens=maxTokens,
        background_tasks=background_tasks,
    )

    return ResponseUtil.success(data=request_id)
