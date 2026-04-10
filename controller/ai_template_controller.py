from fastapi import APIRouter, Depends, BackgroundTasks, Query, Body

from ai.adapters.enums import AIAction
from common.config.get_db import get_db
from common.exception.errors import NotFoundError
from common.response.response_util import ResponseUtil
from core.deps.auth import get_current_user, check_book_owner, check_user_quota_or_raise
from core.entity.schemas import GenerateRequest
from core.entity.vo.ai_model_vo import AiModelResp, DeleteHistoryReq
from service.ai_prompt_service import PromptService
from service.ai_service import AIService
from service.usage_service import UsageService


aiTemplateController = APIRouter(prefix="/ai/template")

@aiTemplateController.post("/execute")
async def execute(
        templateId:str = Body(...),
        userPrompt:str = Body(...),
        user=Depends(get_current_user),
        db=Depends(get_db)):
    return ResponseUtil.success()