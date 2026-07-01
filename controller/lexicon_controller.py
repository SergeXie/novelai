from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from common.config.get_db import get_db
from common.response.response_util import ResponseUtil
from core.deps.auth import get_current_user
from core.entity.vo.base_vo import PageResp
from core.entity.vo.global_lexicon_vo import GlobalLexiconCreateReq, GlobalLexiconDeleteReq, GlobalLexiconEditReq
from service.global_lexicon_service import GlobalLexiconService


lexiconController = APIRouter(prefix="/lexicon")


@lexiconController.post("/create", name="创建公共词条库")
async def create_global_lexicon(
        req: GlobalLexiconCreateReq,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
):
    data = await GlobalLexiconService.create_lexicon(db=db, user_id=user.pkId, req=req)
    return ResponseUtil.success(data=data)


@lexiconController.get("/list", name="公共词条库列表")
async def list_global_lexicons(
        page: int = Query(1, ge=1),
        pageSize: int = Query(20, ge=1, le=100),
        lexiconType: int | None = Query(None, ge=1, le=4),
        title: str | None = Query(None, description="词条名称关键字"),
        keyword: str | None = Query(None, description="词条名称关键字兼容参数"),
        scope: str | None = Query(None, description="public=广场公开, mine=我的发布"),
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
):
    search_title = title if title is not None else keyword
    rows, total = await GlobalLexiconService.list_lexicons(
        db=db,
        user_id=user.pkId,
        page=page,
        page_size=pageSize,
        lexicon_type=lexiconType,
        title=search_title,
        scope=scope,
    )
    return ResponseUtil.success(data=PageResp(list=rows, total=total, page=page, pageSize=pageSize))


@lexiconController.get("/detail", name="公共词条库详情")
async def get_global_lexicon_detail(
        id: int = Query(..., ge=1),
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
):
    data = await GlobalLexiconService.get_detail(db=db, user_id=user.pkId, lexicon_id=id)
    return ResponseUtil.success(data=data)


@lexiconController.post("/edit", name="编辑公共词条库")
async def edit_global_lexicon(
        req: GlobalLexiconEditReq,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
):
    data = await GlobalLexiconService.edit_lexicon(db=db, user_id=user.pkId, req=req)
    return ResponseUtil.success(data=data)


@lexiconController.post("/delete", name="删除公共词条库")
async def delete_global_lexicon(
        req: GlobalLexiconDeleteReq,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
):
    await GlobalLexiconService.delete_lexicon(db=db, user_id=user.pkId, req=req)
    return ResponseUtil.success()
