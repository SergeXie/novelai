import uuid
from typing import List

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.entity.do.book_node import BookNode
from core.entity.do.books import Book


class BookDAO:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_book_nodes(self, bid: str, uid:int) -> List[BookNode]:
        result = await self.db.execute(
            select(BookNode).where(and_(BookNode.bid == bid,
                                        BookNode.uid == uid)).order_by(BookNode.id)
        )
        nodes = result.scalars().all()
        return nodes

    @staticmethod
    async def create_node(
            db: AsyncSession,
            *,
            bid: str,
            uid: int,
            name: str,
            parent_id: int,
            is_leaf: int,
            depth: int,
    ) -> BookNode:
        """
        创建单个书籍节点
        """
        node = BookNode(
            bid=bid,
            uid=uid,
            name=name,
            parent_id=parent_id,
            is_leaf=is_leaf,
            depth=depth,
            content=None,
        )
        db.add(node)
        await db.flush()  #  关键：提前拿到 node.id
        return node

    @staticmethod
    async def create_book(
            db: AsyncSession,
            *,
            uid: int,
            title: str,
            bookType: str,
            description: str | None,
    ) -> Book:
        """
        创建书籍记录
        """
        book = Book(
            uid=uid,
            bid=uuid.uuid4().hex,  # 生成业务层书籍ID
            title=title,
            bookType=bookType,
            description=description,
            status=0,  # 默认草稿
            wordCount=0,
        )

        db.add(book)
        await db.commit()
        await db.refresh(book)
        return book


    @staticmethod
    async def list_books(
            db: AsyncSession,
            *,
            uid: int,
            status: int | None = None,
    ) -> list[Book]:
        """
        查询书籍列表
        """
        stmt = select(Book).where(Book.uid == uid)

        if status is not None:
            stmt = stmt.where(Book.status == status)

        stmt = stmt.order_by(Book.createTime.desc())

        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_node_by_id(
            db: AsyncSession,
            *,
            node_id: int,
            uid: int,
            bid: str,
    ) -> BookNode | None:
        """
        根据 mc_book_node.id 查询节点
        """
        stmt = select(BookNode).where(and_(BookNode.id == node_id,
                                           BookNode.bid == bid,
                                           BookNode.uid == uid))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_node_parent_by_id(
            db: AsyncSession,
            *,
            parent_id: int,
            uid: int,
            bid: str,
    ) -> BookNode | None:
        """
        根据 mc_book_node.id 查询节点
        """
        stmt = select(BookNode).where(and_(BookNode.id == parent_id,
                                           BookNode.bid == bid,
                                           BookNode.uid == uid))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def update_node_content(
            db: AsyncSession,
            *,
            node: BookNode,
            content: str | None,
    ) -> BookNode:
        """
        更新节点内容
        """
        node.content = content
        db.add(node)
        await db.commit()
        await db.refresh(node)
        return node

    @staticmethod
    async def update_node(
            db: AsyncSession,
            node: BookNode,
            *,
            name: str | None,
    ) -> BookNode:
        """
        更新节点名称 / 正文
        """
        if name is not None:
            node.name = name

        db.add(node)
        await db.commit()
        await db.refresh(node)
        return node

    @staticmethod
    async def add_chapter_node(
            db: AsyncSession,
            *,
            uid: int,
            bid: str,
            parent_id: int,
            is_leaf: int,
            name: str,
            depth: int,

    ) -> BookNode:
        """
        新增章节（自动补正文根节点）
        """

        node = BookNode(
            bid=bid,
            uid=uid,
            parent_id=parent_id,
            name=name,
            is_leaf=is_leaf,
            depth=depth,
        )
        db.add(node)
        await db.flush()
        return node

    @staticmethod
    async def get_nodes_by_parent_ids(
        db: AsyncSession,
        parent_ids: list[int],
    ) -> list[BookNode]:
        result = await db.execute(
            select(BookNode).where(BookNode.parent_id.in_(parent_ids))
        )
        return result.scalars().all()

    @staticmethod
    async def delete_nodes(
        db: AsyncSession,
        node_ids: list[int],
    ):
        await db.execute(
            BookNode.__table__.delete().where(
                BookNode.id.in_(node_ids)
            )
        )