from typing import Optional

from fastapi import APIRouter, Depends, Body

from common.config.get_db import get_db
from common.response.response_util import ResponseUtil
from core.deps.auth import get_current_user
from service.prompt_square_service import PromptSquareService

aiTemplateController = APIRouter(prefix="/ai/template")

@aiTemplateController.post("/execute")
async def execute(
        templateKey:str = Body(...),
        level:int = Body(...),
        userPrompt:str = Body(...),
        parameter:Optional[dict] = Body(None),
        template:Optional[float] = Body(None),
        maxTokens:Optional[int] = Body(None),
        user=Depends(get_current_user),
        db=Depends(get_db)):

    request_id = PromptSquareService.execute_by_template(
        db=db,
        level=level,
        template_key=templateKey,
        user_prompt=userPrompt,
        user=user,
        temperature=template,
        max_tokens=maxTokens,
    )

    return ResponseUtil.success(data=request_id)