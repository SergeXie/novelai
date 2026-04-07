import json
from typing import Optional

from fastapi import APIRouter, Depends, Body, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from ai.adapters.enums import AIProvider, AIAction
from ai.ai_nexus import check_ai_input, get_ai_nexus
from ai.workflow.wf_create_book import CreateBookWorkflow
from common.config.generator import LZSDGenerator
from common.config.get_db import get_db
from common.response.response_util import ResponseUtil
from core.deps.auth import get_current_user
from core.entity.vo.prompt_register_vo import PromptRegistryResp
from dao.book_dao import BookDAO
from service.ai_prompt_service import PromptService
from service.ai_service import AIService
from service.usage_service import UsageService

promptController = APIRouter(prefix="/prompts", tags=["提示词管理"])

@promptController.get("/list", name="获取所有提示词模板")
async def list_all_prompts(db: AsyncSession = Depends(get_db)):
    # 实例化 Service 并透传 Session
    service = PromptService(db)

    # 调用 Service 业务
    data = await service.get_all_prompts()

    # 转换为 Schema 并返回
    result = [PromptRegistryResp.model_validate(p) for p in data]
    return ResponseUtil.success(data=result)


@promptController.get("/scopes", name="获取节点默认提示词工具")
async def get_prompts_scopes(scope: int, db: AsyncSession = Depends(get_db)):
    # 实例化 Service 并透传 Session
    service = PromptService(db)

    # 调用 Service 业务
    data = await service.get_scope_detail_prompts(scope)

    # 转换为 Schema 并返回
    result = [PromptRegistryResp.model_validate(p) for p in data]
    return ResponseUtil.success(data=result)


@promptController.get("/contentTools", name="获取正文AI工具列表")
async def get_content_ai_tools(db: AsyncSession = Depends(get_db)):
    # 实例化 Service 并透传 Session
    service = PromptService(db)

    # 调用 Service 业务
    data = await service.get_all_prompts_scope()

    # 转换为 Schema 并返回
    result = [PromptRegistryResp.model_validate(p) for p in data]
    return ResponseUtil.success(data=result)

@promptController.get("/get_book_creation_tool", name="获取创建作品AI工具")
async def get_book_creation_ai_tool(db: AsyncSession = Depends(get_db)):
    prompt_service = PromptService(db)
    data = dict()
    tool = await prompt_service.get_tool_by_key("FhaOjVZT456JWH3P")
    if tool:
        data["title"] = PromptRegistryResp.model_validate(tool)

    tool = await prompt_service.get_tool_by_key("kOtnrNg6CUm5IZfJ")
    if tool:
        data["intro"] = PromptRegistryResp.model_validate(tool)

    return ResponseUtil.success(data=data)

@promptController.post("/render", name="渲染提示词")
async def render(
        background_tasks: BackgroundTasks,
        bid: Optional[str] = Body(None),
        level:int = Body(...),
        tool_key: str = Body(...),
        inputs: dict = Body(...),
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user)
):
    service = PromptService(db)

    book = None
    if bid:
        book_dao = BookDAO(db)
        book = await book_dao.get_book_by_bid(bid=bid, user_id=user.pkId)

    try:
        # 整理提示词
        final_prompt = await service.render_prompt_content(book=book, tool_key=tool_key, inputs=inputs)
        ai_service = AIService(db)
        payload = {
            "tool_key": tool_key,
            **inputs
        }

        # 生成 requestId 并记录初始请求（不阻塞）
        request_id = await ai_service.prepare_and_record_request(
            user=user,
            bid=bid,
            user_prompt=final_prompt,
            level=level,
            temperature=0.7,
            action_type="render",
            correlation=payload,
            background_tasks=background_tasks,
            origin_prompt=""
        )
        return ResponseUtil.success(data={"request_id": request_id})
    except ValueError as e:
        return ResponseUtil.error(msg=str(e))


@promptController.post("/create_book", name="小说工作流生成")
async def create_book_flow(
        idea: str = Body(..., description="小说脑洞/主题"),
        level:int = Body(..., description="模型"),
        user:Depends = Depends(get_current_user)
):

    check_ai_input(idea)

    try:
        ai_provider = AIProvider.from_level(level)
        nexus = get_ai_nexus()

        # 1. 校验配额-
        async with get_db() as db:
            # 使用上下文管理器确保即使出错也能关闭
            usage_service = UsageService(db)
            await usage_service.check_quota_or_raise(
                user_info=user,
                frozen_token_length=nexus.get_actual_tokens(provider=ai_provider, content=idea)
            )

        workflow = CreateBookWorkflow(ai_provider=ai_provider)

        context = {"idea": idea}
        workflow_rsp = await workflow.run(initial_context=context)

        """
            解析文源 AI 创作流水线数据
        """
        result = {
            "title": "",
            "summary": "",
            "characters": []
        }

        token_usage = 0

        # 遍历 steps 提取数据
        for step in workflow_rsp.steps:
            result = step.result
            step_name = step.name
            token_usage += result.usage.total_tokens

            # 2. 二次解析内部的 output 字符串
            output_data = json.loads(step.result.content)

            if step_name == "title_and_blurb":
                result["title"] = output_data.get("title")
                result["summary"] = output_data.get("blurb")

            elif step_name == "people":
                result["characters"] = output_data.get("characters", [])

        async with get_db() as db:
            usage_service = UsageService(db)
            await usage_service.record(
                user_id=user.pkId,
                level=level,
                bid="",
                user_prompt=workflow.name,
                origin_prompt=idea,
                request_id=LZSDGenerator.generate_request_id(),
                system_prompt=workflow_rsp.final_result.system_prompt,
                output_content=workflow_rsp.final_result.output_content,
                action_type=AIAction.WorkFlow,
                temperature=0.7
            )

        return ResponseUtil.success(data=result)

    except Exception as e:
        return ResponseUtil.error(msg=f"执行失败: {str(e)}")