import json
from typing import Optional
from fastapi import APIRouter, Depends, Body, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from ai.adapters.enums import AIProvider, AIAction
from ai.ai_nexus import check_ai_input
from ai.workflow.wf_create_book import CreateBookWorkflow
from common.config.config import settings
from common.config.generator import LZSDGenerator
from common.config.get_db import get_db, get_db_context
from common.response.response_util import ResponseUtil
from core.deps.auth import get_current_user, check_user_quota_or_raise
from core.entity.vo.ai_response import TokenUsage
from core.entity.vo.prompt_register_vo import PromptRegistryResp
from core.entity.vo.prompt_square_vo import PromptSquareCreateReq, PromptSquareUpdateReq
from dao.book_dao import BookDAO
from service.ai_prompt_service import PromptService
from service.ai_service import AIService
from service.prompt_square_service import PromptSquareService
from service.usage_service import UsageService

promptController = APIRouter(prefix="/prompts", tags=["提示词管理"])



@promptController.get("/publicPrivatePromptList", name="提示词广场模板库")
async def get_public_private_prompt_list(
    page: int = Query(1, ge=1),
    pageSize: int = Query(10, le=50),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    获取公开提示词列表（分页）
    """

    data, total = await PromptSquareService.get_public_list(
        db,
        page,
        pageSize,
        category
    )

    return ResponseUtil.success(data=data, dict_content={
            "page": page,
            "pageSize": pageSize,
            "total": total,
            "category": category
        })


@promptController.get("/publicCategories", name="获取提示词分类")
async def get_public_prompt_categories(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    获取提示词广场分类列表，按 category 去重
    """
    data = await PromptSquareService.get_public_categories(db)
    return ResponseUtil.success(data=data)


@promptController.post("/promptSquare", name="创建用户提示词")
async def create_user_prompt_square(
    req: PromptSquareCreateReq,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    创建用户自己的提示词广场数据
    """
    data = await PromptSquareService.create_user_prompt(db, user.pkId, req)
    return ResponseUtil.success(data=data)


@promptController.put("/promptSquare", name="修改用户提示词")
async def update_user_prompt_square(
    req: PromptSquareUpdateReq,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    修改用户自己的提示词广场数据
    """
    data = await PromptSquareService.update_user_prompt(db, user.pkId, req)
    if not data:
        return ResponseUtil.failure(msg="提示词不存在或无权限修改")
    return ResponseUtil.success(data=data)


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
    tool = await prompt_service.get_tool_by_key("wenyuan_title_forge")
    if tool:
        data["title"] = PromptRegistryResp.model_validate(tool)

    tool = await prompt_service.get_tool_by_key("wenyuan_blurb_forge")
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
    # 检查用户额度
    await check_user_quota_or_raise(frozen_token_length=3000, user_info=user)

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

    # 1. 校验配额-
    await check_user_quota_or_raise(frozen_token_length=3000, user_info=user)

    try:
        ai_provider = AIProvider.from_level(level)
        workflow = CreateBookWorkflow(ai_provider=ai_provider)
        context = {"idea": idea}
        try:
            print(">>> 准备进入工作流...")
            # 传入副本，彻底隔离外部 context 受到污染的可能性
            workflow_rsp = await workflow.run(initial_context=context.copy())
            print(">>> 工作流执行成功，返回类型为:", type(workflow_rsp))

        except Exception as e:
            raise e

        """
            解析文源 AI 创作流水线数据
        """

        # --- 解析文源 AI 创作流水线数据 ---
        final_result_data = {
            "title": "",
            "summary": "",
            "characters": [],
        }

        usage = TokenUsage()

        # 遍历 steps 提取数据
        for step_data in workflow_rsp.steps:
            # 注意：根据你之前的修改，step_data 现在很可能是一个 dict
            # 如果 AIWorkFlowStepResponse 也是普通类，则用 .name；如果是 dict 用 ["name"]
            # 建议统一检查一下
            s_name = step_data.name if hasattr(step_data, 'name') else step_data["name"]
            s_result = step_data.result if hasattr(step_data, 'result') else step_data["result"]

            # 提取 token (处理 dict 格式)
            if isinstance(s_result, dict):
                usage.total_tokens += s_result.get("usage", {}).get("total_tokens", 0)
                usage.completion_tokens += s_result.get("usage", {}).get("completion_tokens", 0)
                usage.prompt_tokens += s_result.get("usage", {}).get("prompt_tokens", 0)
                content_str = s_result.get("content", "")
            else:
                usage.total_tokens += s_result.usage.total_tokens
                usage.completion_tokens += s_result.usage.completion_tokens
                usage.prompt_tokens += s_result.usage.prompt_tokens
                content_str = s_result.content

            # 解析内部 JSON
            try:
                output_data = json.loads(content_str)
                if s_name == "title_and_blurb":
                    final_result_data["title"] = output_data.get("title")
                    final_result_data["summary"] = output_data.get("blurb")
                elif s_name == "people":
                    final_result_data["characters"] = output_data.get("characters", [])
            except Exception as e:
                print(f"解析步骤 {s_name} 失败: {e}")

        final_result_data["usage"] = usage.model_dump()

        # 提取最终结果数据
        final_obj = workflow_rsp.final_result
        is_dict = isinstance(final_obj, dict)

        async with get_db_context() as db:
            request_id = LZSDGenerator.generate_request_id()
            usage_service = UsageService(db)
            await usage_service.record(
                user_id=user.pkId,
                level=level,
                bid="",
                user_prompt="一键成书",
                origin_prompt=idea,
                request_id=request_id,
                # 兼容字典和对象访问
                system_prompt="",  # 如果 AICompletionResponse 没存 system_prompt，传空
                output_content=final_obj.get("content", "") if is_dict else final_obj.content,
                action_type=AIAction.WorkFlow,
                temperature=0.7,
                totalTokens=usage.total_tokens,
                promptTokens=usage.prompt_tokens,
                completionTokens=usage.completion_tokens,
            )

            await usage_service.record_consumption(request_id=request_id, total_tokens=usage.total_tokens, multiplier=settings.MULTIPLIER)

        return ResponseUtil.success(data=final_result_data)

    except Exception as e:
        return ResponseUtil.error(msg=f"执行失败: {str(e)}")
