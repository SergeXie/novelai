from typing import Optional
from fastapi import APIRouter, Depends, Body
from fastapi.params import Query
from sqlalchemy.ext.asyncio import AsyncSession
from common.config.get_db import get_db
from common.response.response_util import ResponseUtil
from core.deps.auth import get_current_user
from core.entity.vo.base_vo import PageResp
from core.entity.vo.prompt_square_vo import PromptSquareDetailReq, PromptSquareUpdateReq, PromptSquareCreateReq
from service.prompt_square_service import PromptSquareService

aiTemplateController = APIRouter(prefix="/ai/template")

@aiTemplateController.post("/execute", name="广场模板提示词生成推理")
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




@aiTemplateController.get("/publicPromptList", name="提示词广场模板库")
async def get_public_private_prompt_list(
    page: int = Query(1, ge=1),
    pageSize: int = Query(10, le=50),
    category: Optional[str] = Query(None),
    promptType: str = Query("public"),
    title: Optional[str] = Query(None),  # 新增
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    获取提示词列表（支持筛选：公开 / 我的）
    """

    data, total = await PromptSquareService.get_public_list(
        db,
        page,
        pageSize,
        category,
        user.pkId,
        promptType,
        title
    )
    rsp_data = PageResp(list=data, total=total, pageSize=pageSize, page=page)
    return ResponseUtil.success(data=rsp_data)


@aiTemplateController.get("/publicCategories", name="获取提示词分类")
async def get_public_prompt_categories(
    db: AsyncSession = Depends(get_db)
):
    """
    获取提示词广场分类列表，按 category 去重
    """
    data = await PromptSquareService.get_public_categories(db)
    return ResponseUtil.success(data=data)


@aiTemplateController.post("/createPromptSquare", name="创建用户提示词广场")
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
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    data, total = await PromptSquareService.get_my_favor_list(
        db,
        user.pkId,
        page,
        pageSize,
        title
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