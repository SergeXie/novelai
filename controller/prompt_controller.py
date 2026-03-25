from fastapi import APIRouter, Depends, Body, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from common.config.get_db import get_db
from common.response.response_util import ResponseUtil
from core.deps.auth import get_login_user, check_book_owner
from core.entity.vo.prompt_register_vo import PromptRegistryResp
from service.ai_prompt_service import PromptService
from service.ai_service import AIService
from service.novel_workflow_demo import WorkflowError, run_novel_workflow

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
async def get_contentTools(db: AsyncSession = Depends(get_db), user=Depends(get_login_user)):
    # 实例化 Service 并透传 Session
    service = PromptService(db)

    # 调用 Service 业务
    data = await service.get_all_prompts_scope()

    # 转换为 Schema 并返回
    result = [PromptRegistryResp.model_validate(p) for p in data]
    return ResponseUtil.success(data=result)

@promptController.get("/get_book_creation_tool", name="获取创建作品AI工具")
async def get_book_creation(db: AsyncSession = Depends(get_db)):
    prompt_service = PromptService(db)
    data = []
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
        bid: str = Body(...),
        level:int = Body(...),
        tool_key: str = Body(...),
        inputs: dict = Body(...),
        db: AsyncSession = Depends(get_db),
        user=Depends(get_login_user),
        book=Depends(check_book_owner),
):
    service = PromptService(db)
    try:
        # 整理提示词
        final_prompt = await service.render_prompt_content(user_id=user.pkId, book=book, tool_key=tool_key, inputs=inputs)
        ai_service = AIService(db)
        payload = {
            "tool_key": tool_key,
            **inputs
        }

        # 生成 requestId 并记录初始请求（不阻塞）
        request_id = await ai_service.prepare_and_record_request(
            user_id=user.pkId,
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


@promptController.post("/workflow", name="小说工作流生成")
async def workflow(
        idea: str = Body(..., description="小说脑洞/主题"),
        model: str | None = Body(None, description="可选模型名称，默认读取 DOUBAO__MODEL_NAME"),
        default_system: str | None = Body(None, description="可选默认系统提示词"),
):
    try:
        data = await run_in_threadpool(
            run_novel_workflow,
            idea=idea,
            model=model,
            default_system=default_system,
        )
        return ResponseUtil.success(data=data)
    except WorkflowError as e:
        return ResponseUtil.error(msg=str(e))
    except Exception as e:
        return ResponseUtil.error(msg=f"工作流执行失败: {str(e)}")