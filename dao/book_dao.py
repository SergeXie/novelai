from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.entity.do.book_node import BookNode


class BookDAO:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_book_nodes(self, bid: str) -> List[BookNode]:
        result = await self.db.execute(
            select(BookNode).where(BookNode.bid == bid).order_by(BookNode.id)
        )
        nodes = result.scalars().all()
        return nodes