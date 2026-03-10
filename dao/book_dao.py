import uuid
from typing import List, Optional

from sqlalchemy import select, and_, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.entity.do.book_node import BookNode
from core.entity.do.books import Book


class BookDAO:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_book_nodes(self, bid: str, uid:int, max_depth: Optional[int] = None) -> List[BookNode]:
        """
            获取书籍节点列表
            :param bid: 书籍ID
            :param uid: 用户ID
            :param max_depth: 最大深度限制（可选）
            """
        # 1. 基础查询条件
        stmt = select(BookNode).where(
            and_(
                BookNode.bid == bid,
                BookNode.uid == uid
            )
        )

        # 2. 动态添加深度限制
        if max_depth is not None:
            # 增加 depth <= max_depth 的限制
            stmt = stmt.where(BookNode.depth <= max_depth)

        # 3. 排序执行
        stmt = stmt.order_by(BookNode.id)

        result = await self.db.execute(stmt)
        nodes = result.scalars().all()
        return list(nodes)

    @staticmethod
    async def get_book_nodes_list(db: AsyncSession, correlation: list, uid:int):
        result = await db.execute(
            select(BookNode.name, BookNode.content).where(and_(BookNode.id.in_(correlation),
                                                BookNode.uid == uid)).order_by(BookNode.id)
        )
        nodes = [str(item) for row in result for item in row if item is not None]
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
            depth: int
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
            content=None
        )
        db.add(node)
        await db.flush()  #  关键：提前拿到 node.id
        return node

    @staticmethod
    async def create_book(
            db: AsyncSession,
            uid: int,
            title: str,
            bookType: str,
            description: str | None,
            template_id: str | None,
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
            template_id=template_id
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
            data: dict | None = None,
    ) -> BookNode:
        """
        更新节点内容
        """
        if content is not None:
            node.content = content
        if data is not None:
            node.data = data
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
            data: dict | None = None,
    ) -> BookNode:
        """
        更新节点名称 / 正文
        """
        if name is not None:
            node.name = name
        if data is not None:
            node.data = data

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
            data: dict | None = None,
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
            data=data,
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

    @staticmethod
    async def get_book_by_bid(
            db: AsyncSession,
            bid: str,
            uid:int
    ) -> Book | None:
        result = await db.execute(
            select(Book).where(Book.bid == bid, Book.uid == uid)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update_book_status(
            db: AsyncSession,
            *,
            bid: str,
            status: int,
    ):
        await db.execute(
            update(Book)
            .where(Book.bid == bid)
            .values(status=status)
        )

    @staticmethod
    async def update_book(
            db: AsyncSession,
            *,
            bid: str,
            uid: int,
            values: dict,
    ):
        """
        按需更新书籍字段
        """
        if not values:
            return

        await db.execute(
            update(Book)
            .where(and_(Book.bid == bid, Book.uid == uid))
            .values(**values)
        )


    @staticmethod
    async def delete_nodes_by_bid(
        db: AsyncSession,
        bid: str,
        uid: int,

    ):
        await db.execute(
            delete(BookNode).where(and_(BookNode.bid == bid, BookNode.uid == uid))
        )

    @staticmethod
    async def hard_delete_book(
            db: AsyncSession,
            bid: str,
            uid: int,

    ):
        await db.execute(
            delete(Book).where(and_(Book.bid == bid, Book.uid == uid))
        )