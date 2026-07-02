from sqlalchemy.ext.asyncio import AsyncSession

from common.exception.lzsd_exception import ServiceWarning
from core.entity.do.global_lexicon_do import McGlobalLexicon
from core.entity.vo.global_lexicon_vo import (
    GlobalLexiconCreateReq,
    GlobalLexiconCreateResp,
    GlobalLexiconDeleteReq,
    GlobalLexiconEditReq,
    GlobalLexiconListItem,
)
from dao.global_lexicon_dao import GlobalLexiconDAO


class GlobalLexiconService:
    @staticmethod
    def to_item(lexicon: McGlobalLexicon) -> GlobalLexiconListItem:
        return GlobalLexiconListItem(
            id=lexicon.id,
            userId=lexicon.user_id,
            title=lexicon.title,
            lexiconType=lexicon.lexicon_type,
            content=lexicon.content,
            data=lexicon.data,
            shareLevel=lexicon.share_level,
            createTime=lexicon.create_time,
        )

    @staticmethod
    async def create_lexicon(
            db: AsyncSession,
            user_id: int,
            req: GlobalLexiconCreateReq,
    ) -> GlobalLexiconCreateResp:
        title = (req.title or "").strip()
        if not title:
            raise ServiceWarning("词条名称不能为空")

        lexicon = McGlobalLexicon(
            user_id=user_id,
            title=title,
            lexicon_type=req.lexiconType,
            content=req.content,
            data=req.data,
            share_level=req.shareLevel,
        )
        lexicon = await GlobalLexiconDAO.create(db, lexicon)

        return GlobalLexiconCreateResp(**GlobalLexiconService.to_item(lexicon).model_dump())

    @staticmethod
    async def edit_lexicon(
            db: AsyncSession,
            user_id: int,
            req: GlobalLexiconEditReq,
    ) -> GlobalLexiconListItem:
        lexicon = await GlobalLexiconDAO.get_user_lexicon(db, req.id, user_id)
        if not lexicon:
            raise ServiceWarning("词条不存在或无权限修改")

        update_fields = req.model_fields_set
        if "title" in update_fields:
            title = (req.title or "").strip()
            if not title:
                raise ServiceWarning("词条名称不能为空")
            lexicon.title = title
        if "lexiconType" in update_fields or "lexicon_type" in update_fields:
            if req.lexiconType is None:
                raise ServiceWarning("词条类型不能为空")
            lexicon.lexicon_type = req.lexiconType
        if "content" in update_fields:
            lexicon.content = req.content
        if "data" in update_fields:
            lexicon.data = req.data
        if "shareLevel" in update_fields or "share_level" in update_fields:
            if req.shareLevel is None:
                raise ServiceWarning("共享等级不能为空")
            lexicon.share_level = req.shareLevel

        await db.flush()
        await db.refresh(lexicon)
        return GlobalLexiconService.to_item(lexicon)

    @staticmethod
    async def delete_lexicon(
            db: AsyncSession,
            user_id: int,
            req: GlobalLexiconDeleteReq,
    ) -> bool:
        lexicon = await GlobalLexiconDAO.get_user_lexicon(db, req.id, user_id)
        if not lexicon:
            raise ServiceWarning("词条不存在或无权限删除")

        await GlobalLexiconDAO.delete(db, lexicon)
        return True

    @staticmethod
    async def list_lexicons(
            db: AsyncSession,
            user_id: int,
            page: int | None,
            page_size: int | None,
            lexicon_type: int | None = None,
            title: str | None = None,
            scope: str | None = None,
    ) -> tuple[list[GlobalLexiconListItem], int]:
        scope = (scope or "").strip() or None
        if lexicon_type is not None and lexicon_type not in (1, 2, 3, 4):
            raise ServiceWarning("词条类型不正确")
        if scope is not None and scope not in ("public", "mine"):
            raise ServiceWarning("筛选范围不正确")

        rows, total = await GlobalLexiconDAO.list_page(
            db=db,
            user_id=user_id,
            page=page,
            page_size=page_size,
            lexicon_type=lexicon_type,
            title=(title or "").strip() or None,
            scope=scope,
        )
        return [GlobalLexiconService.to_item(item) for item in rows], total

    @staticmethod
    async def get_detail(
            db: AsyncSession,
            user_id: int,
            lexicon_id: int,
    ) -> GlobalLexiconListItem:
        lexicon = await GlobalLexiconDAO.get_visible_lexicon(db, lexicon_id, user_id)
        if not lexicon:
            raise ServiceWarning("词条不存在或无权限查看")
        return GlobalLexiconService.to_item(lexicon)
