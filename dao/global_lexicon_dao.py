from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.entity.do.global_lexicon_do import McGlobalLexicon


class GlobalLexiconDAO:
    @staticmethod
    async def create(db: AsyncSession, lexicon: McGlobalLexicon) -> McGlobalLexicon:
        db.add(lexicon)
        await db.flush()
        await db.refresh(lexicon)
        return lexicon

    @staticmethod
    async def get_user_lexicon(db: AsyncSession, lexicon_id: int, user_id: int) -> McGlobalLexicon | None:
        stmt = select(McGlobalLexicon).where(
            McGlobalLexicon.id == lexicon_id,
            McGlobalLexicon.user_id == user_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_visible_lexicon(db: AsyncSession, lexicon_id: int, user_id: int) -> McGlobalLexicon | None:
        stmt = select(McGlobalLexicon).where(
            McGlobalLexicon.id == lexicon_id,
            or_(
                McGlobalLexicon.user_id == user_id,
                McGlobalLexicon.share_level == 2,
            ),
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def delete(db: AsyncSession, lexicon: McGlobalLexicon) -> None:
        await db.delete(lexicon)
        await db.flush()

    @staticmethod
    async def list_page(
            db: AsyncSession,
            user_id: int,
            page: int,
            page_size: int,
            lexicon_type: int | None = None,
            title: str | None = None,
            scope: str | None = None,
    ) -> tuple[list[McGlobalLexicon], int]:
        if scope == "public":
            conditions = [McGlobalLexicon.share_level == 2]
        elif scope == "mine":
            conditions = [McGlobalLexicon.user_id == user_id]
        else:
            conditions = [
                or_(
                    McGlobalLexicon.user_id == user_id,
                    McGlobalLexicon.share_level == 2,
                )
            ]
        if lexicon_type is not None:
            conditions.append(McGlobalLexicon.lexicon_type == lexicon_type)
        if title:
            conditions.append(McGlobalLexicon.title.contains(title, autoescape=True))

        count_stmt = select(func.count()).select_from(McGlobalLexicon).where(*conditions)
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = (
            select(McGlobalLexicon)
            .where(*conditions)
            .order_by(McGlobalLexicon.create_time.desc(), McGlobalLexicon.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all()), total
