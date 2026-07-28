from typing import Optional
from fastapi.params import Query
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Body, BackgroundTasks

from ai.adapters.enums import AIAction
from common.config.get_db import get_db
from common.response.response_util import ResponseUtil
from core.deps.auth import get_current_user, check_user_quota_or_raise, check_book_owner
from core.entity.vo.base_vo import PageResp
from core.entity.vo.prompt_square_vo import PromptSquareDetailReq, PromptSquareUpdateReq, PromptSquareCreateReq
from core.enums.prompt_sys_var import PromptTopCategory
from service.ai_service import AIService
from service.menu_service import MenuService
from service.prompt_square_service import PromptSquareService

aiTemplateController = APIRouter(prefix="/ai/template")


@aiTemplateController.post("/execute")
async def execute(
        background_tasks: BackgroundTasks,
        templateKey: Optional[str] = Body(None),
        level: int = Body(...),
        user_prompt: str = Body(""),
        bid: Optional[str] = Body(None),
        inputs: Optional[dict] = Body(None),
        correlation: Optional[list] = Body(None),
        lexicon_ids: Optional[list[int]] = Body(None, description="关联的公共词条ID列表"),
        temperature: Optional[float] = Body(None),
        max_tokens: Optional[int] = Body(None),
        user=Depends(get_current_user),
        db=Depends(get_db)):
    if bid:
        await check_book_owner(bid=bid, db=db, user=user)

    ai_service = AIService(db=db)
    request_id = await ai_service.execute(db=db,
                                          user=user,
                                          action_type=AIAction.Execute,
                                          level=level,
                                          temperature=temperature,
                                          max_tokens=max_tokens,
                                          bid=bid,
                                          user_prompt=user_prompt,
                                          correlation=correlation,
                                          lexicon_ids=lexicon_ids,
                                          template_key=templateKey,
                                          inputs=inputs,
                                          background_tasks=background_tasks)

    return ResponseUtil.success(data=request_id)


@aiTemplateController.post("/executeFixed", name="角色分析")
async def execute_fixed(
        background_tasks: BackgroundTasks,
        level: int = Body(...),
        user_prompt: str = Body(""),
        bid: Optional[str] = Body(None),
        inputs: Optional[dict] = Body(None),
        correlation: Optional[list] = Body(None),
        lexicon_ids: Optional[list[int]] = Body(None, description="关联的公共词条ID列表"),
        temperature: Optional[float] = Body(None),
        max_tokens: Optional[int] = Body(None),
        user=Depends(get_current_user),
        db=Depends(get_db)):
    """
    固定模板执行AI（templateKey 固定为 PRMTZJLVQDNYBXCGHS）
    """
    FIXED_TEMPLATE_KEY = "PRMTZJLVQDNYBXCGHS"

    if bid:
        await check_book_owner(bid=bid, db=db, user=user)

    ai_service = AIService(db=db)
    request_id = await ai_service.execute(db=db,
                                          user=user,
                                          action_type=AIAction.Execute,
                                          level=level,
                                          temperature=temperature,
                                          max_tokens=max_tokens,
                                          bid=bid,
                                          user_prompt=user_prompt,
                                          correlation=correlation,
                                          lexicon_ids=lexicon_ids,
                                          template_key=FIXED_TEMPLATE_KEY,
                                          inputs=inputs,
                                          background_tasks=background_tasks)

    return ResponseUtil.success(data=request_id)



@aiTemplateController.post("/executeFixedTitle", name="章节标题生成")
async def execute_fixed_title(
        background_tasks: BackgroundTasks,
        level: int = Body(...),
        user_prompt: str = Body(""),
        bid: Optional[str] = Body(None),
        inputs: Optional[dict] = Body(None),
        correlation: Optional[list] = Body(None),
        lexicon_ids: Optional[list[int]] = Body(None, description="关联的公共词条ID列表"),
        temperature: Optional[float] = Body(None),
        max_tokens: Optional[int] = Body(None),
        user=Depends(get_current_user),
        db=Depends(get_db)):
    """
    固定模板执行AI（templateKey 固定为 PRMTZJLVQDNYBXCGHS）
    """
    FIXED_TEMPLATE_KEY = "PRMTVIQPUPIHMSUSIFLQ"

    if bid:
        await check_book_owner(bid=bid, db=db, user=user)

    ai_service = AIService(db=db)
    request_id = await ai_service.execute(db=db,
                                          user=user,
                                          action_type=AIAction.Execute,
                                          level=level,
                                          temperature=temperature,
                                          max_tokens=max_tokens,
                                          bid=bid,
                                          user_prompt=user_prompt,
                                          correlation=correlation,
                                          lexicon_ids=lexicon_ids,
                                          template_key=FIXED_TEMPLATE_KEY,
                                          inputs=inputs,
                                          background_tasks=background_tasks)

    return ResponseUtil.success(data=request_id)


@aiTemplateController.get("/publicPromptList", name="提示词广场模板库")
async def get_public_private_prompt_list(
        page: int = Query(1, ge=1),
        pageSize: int = Query(10, le=50),
        category: Optional[str] = Query(None),
        tag: Optional[str] = Query(None),
        promptType: str = Query("public"),
        title: Optional[str] = Query(None),  # 新增
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user)
):
    """
    获取提示词列表（支持筛选：公开 / 我的）
    """

    data, total = await PromptSquareService.get_public_list(
        db=db,
        page=page,
        pageSize=pageSize,
        category=category,
        tag=tag,
        user_id=user.pkId,
        promptType=promptType,
        title=title,
        parent_category=PromptTopCategory.CREATION.code,
    )
    rsp_data = PageResp(list=data, total=total, pageSize=pageSize, page=page)
    return ResponseUtil.success(data=rsp_data)

@aiTemplateController.get("/categories", name="获取提示词分类")
async def get_public_prompt_categories(
        db: AsyncSession = Depends(get_db)
):
    """
    获取提示词广场分类列表，按 category 去重
    """
    data = PromptSquareService.get_prompt_categories()
    return ResponseUtil.success(data=data)


@aiTemplateController.get("/publicCategories", name="获取提示词分类")
async def get_public_prompt_categories(
        db: AsyncSession = Depends(get_db)
):
    """
    获取提示词广场分类列表，按 category 去重
    """
    data = await MenuService.list_prompt_square_labels(db)
    return ResponseUtil.success(data=data)


@aiTemplateController.get("/creationCategories", name="协同创作工具分类")
async def get_creation_categories(db: AsyncSession = Depends(get_db)):
    data = await MenuService.list_creation_categories(db)
    return ResponseUtil.success(data=data)


@aiTemplateController.get("/creationMenus", name="协同创作工具菜单")
async def get_creation_categories(db: AsyncSession = Depends(get_db)):
    data = await MenuService.list_creation_categories(db)
    return ResponseUtil.success(data=data)


@aiTemplateController.get("/promtListByCategory", name="根据协同创作分类获取提示词模板")
async def get_prompt_list_by_category(
        category: str = Query(..., description="协同创作分类key"),
        db: AsyncSession = Depends(get_db),
):
    data = await PromptSquareService.get_prompt_list(db, category=category, parent_category=PromptTopCategory.CREATION)
    return ResponseUtil.success(data=data)


@aiTemplateController.post("/createPromptSquare", name="创建用户提示词广场")
async def create_user_prompt_square(
        req: PromptSquareCreateReq,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
):
    """
    创建用户自己的提示词广场数据
    """
    data = await PromptSquareService.create_user_prompt(db, user_id=user.pkId, title=req.title,
                                                        description=req.description, category=req.category,
                                                        content=req.content,
                                                        background_tasks=background_tasks)
    return ResponseUtil.success(data=data)


@aiTemplateController.get("/detail", name="获取用户提示词详情")
async def get_user_prompt_detail(
        template_key: str,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user)
):
    """
    获取提示词详情（支持公开 / 官方 / 自己）
    """
    data = await PromptSquareService.get_user_prompt_detail(db, user.pkId, template_key)
    if not data:
        return ResponseUtil.failure(msg="提示词不存在或无权限查看")
    return ResponseUtil.success(data=data)


@aiTemplateController.post("/updatePromptSquare", name="修改用户提示词")
async def update_user_prompt_square(
        background_tasks: BackgroundTasks,
        req: PromptSquareUpdateReq,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user)
):
    """
    修改用户自己的提示词广场数据
    """
    data = await PromptSquareService.update_user_prompt(db, user.pkId, req, background_tasks)
    if not data:
        return ResponseUtil.failure(msg="提示词不存在或无权限修改")
    return ResponseUtil.success(data=data)


@aiTemplateController.post("/deletePromptSquare", name="删除用户提示词")
async def delete_user_prompt_square(
        req: PromptSquareDetailReq,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user)
):
    """
    删除用户自己的提示词（物理删除）
    """

    success = await PromptSquareService.delete_user_prompt(
        db,
        user.pkId,
        req.template_key
    )

    if not success:
        return ResponseUtil.failure(msg="提示词不存在或无权限删除")

    return ResponseUtil.success()


@aiTemplateController.get("/myFavorList", name="我的收藏列表")
async def get_my_favor_list(
        page: int = Query(1, ge=1),
        pageSize: int = Query(20, le=50),
        title: Optional[str] = Query(None),  # 新增
        category: Optional[str] = Query(None),
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user)
):
    data, total = await PromptSquareService.get_my_favor_list(
        db,
        user.pkId,
        page,
        pageSize,
        title,
        category
    )

    rsp_data = PageResp(list=data, total=total, pageSize=pageSize, page=page)
    return ResponseUtil.success(data=rsp_data)


@aiTemplateController.post("/favor", name="收藏提示词")
async def favor_prompt(
        req: PromptSquareDetailReq,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user)
):
    success = await PromptSquareService.favor(
        db,
        user.pkId,
        req.template_key
    )

    return ResponseUtil.success()


@aiTemplateController.post("/unfavor", name="取消收藏提示词")
async def unfavor_prompt(
        req: PromptSquareDetailReq,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user)
):
    success = await PromptSquareService.unfavor(
        db,
        user.pkId,
        req.template_key
    )

    return ResponseUtil.success()
