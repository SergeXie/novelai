import uuid
from typing import List, Optional

from sqlalchemy import select, and_, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.entity.do.book_node import BookNode
from core.entity.do.books import Book


class BookDAO:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_book_by_bid(self, user_id:int, bid: str) -> Optional[Book]:
        stmt = select(BookNode).where(
            and_(
                BookNode.bid == bid,
                BookNode.uid == user_id
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_book_nodes(self, bid: str, user_id:int, max_depth: Optional[int] = None) -> List[BookNode]:
        """
            获取书籍节点列表
            :param bid: 书籍ID
            :param user_id: 用户ID
            :param max_depth: 最大深度限制（可选）
            """
        # 1. 基础查询条件
        stmt = select(BookNode).where(
            and_(
                BookNode.bid == bid,
                BookNode.uid == user_id
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

    async def get_book_node_list(self, user_id:int, bid:str, correlation: list)->List[BookNode]:
        result = await self.db.execute(
            select(BookNode).where(and_(BookNode.id.in_(correlation), BookNode.uid==user_id, BookNode.bid==bid)).order_by(BookNode.type)
        )
        nodes = result.scalars().all()
        return list(nodes)

    async def create_book(self,
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

        self.db.add(book)
        await self.db.commit()
        await self.db.refresh(book)
        return book

    async def list_books(
            self,
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

        result = await self.db.execute(stmt)
        books = result.scalars().all()
        return list(books)

    async def get_node_by_id(
            self,
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
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_node_parent_by_id(
            self,
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
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_node_content(
            self,
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
        self.db.add(node)

        await self.db.commit()
        await self.db.refresh(node)
        return node

    async def update_node(
            self,
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

        self.db.add(node)
        await self.db.commit()
        await self.db.refresh(node)
        return node

    async def add_chapter_node(
            self,
            uid: int,
            bid: str,
            parent_id: int,
            is_leaf: int,
            name: str,
            depth: int,
            type: int,
            data: dict | None = None,
            content: str | None = None,
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
            content=content,
            type=type
        )
        self.db.add(node)
        await self.db.flush()
        return node

    async def get_nodes_by_parent_ids(
        self,
        parent_ids: list[int],
    ) -> list[BookNode]:
        result = await self.db.execute(
            select(BookNode).where(BookNode.parent_id.in_(parent_ids))
        )
        nodes = result.scalars().all()
        return list(nodes)

    async def delete_nodes(
            self,
            uid:int,
            bid:str,
            node_ids: list[int],
    ):
        """
            安全删除节点：校验归属关系并执行事务
            """
        if not node_ids:
            return

        # 1. 使用标准的 delete 语句并增加 uid/bid 校验（防止越权）
        stmt = (
            delete(BookNode)
            .where(
                and_(
                    BookNode.id.in_(node_ids),
                    BookNode.uid == uid,
                    BookNode.bid == bid
                )
            )
        )

        # 2. 执行删除
        await self.db.execute(stmt)
        await self.db.commit()


    async def get_book_by_bid(
            self,
            bid: str,
            uid:int
    ) -> Book | None:
        result = await self.db.execute(
            select(Book).where(Book.bid == bid, Book.uid == uid)
        )
        return result.scalar_one_or_none()


    async def update_book_status(
            self,
            bid: str,
            status: int,
    ):
        await self.db.execute(
            update(Book)
            .where(Book.bid == bid)
            .values(status=status)
        )


    async def update_book(
            self,
            bid: str,
            uid: int,
            values: dict,
    ):
        """
        按需更新书籍字段
        """
        if not values:
            return

        await self.db.execute(
            update(Book)
            .where(and_(Book.bid == bid, Book.uid == uid))
            .values(**values)
        )


    async def delete_nodes_by_bid(
        self,
        bid: str,
        uid: int,

    ):
        await self.db.execute(
            delete(BookNode).where(and_(BookNode.bid == bid, BookNode.uid == uid))
        )


    async def hard_delete_book(
            self,
            bid: str,
            uid: int,

    ):
        await self.db.execute(
            delete(Book).where(and_(Book.bid == bid, Book.uid == uid))
        )