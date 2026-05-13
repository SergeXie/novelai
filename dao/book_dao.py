from datetime import datetime
from typing import List, Optional

from loguru import logger
from sqlalchemy import select, and_, update, delete, insert, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from common.utils.generator import LZSDGenerator
from common.utils.text_util import strip_html_tags
from core.entity.do.book_deconstruct_record_do import BookDeconstructRecord
from core.entity.do.book_node import BookNode
from core.entity.do.books import Book
from core.entity.do.generate_log import AiNovelGenerateLog
from core.enums.node_type import BookNodeCategory
from core.processor.book_processor import Chapter

class BookDAO:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_contents_grouped(self, bids: list[str]):

        stmt = select(
            BookNode.bid,
            BookNode.content
        ).where(
            BookNode.bid.in_(bids)
        )

        result = await self.db.execute(stmt)

        rows = result.all()

        data_map = {}

        for bid, content in rows:
            if not content:
                continue

            data_map.setdefault(bid, []).append(content)

        return data_map

    async def get_contents_by_bid(self, bid: str) -> list[str]:

        stmt = select(BookNode.content).where(
            BookNode.bid == bid
        )

        result = await self.db.execute(stmt)

        contents = result.scalars().all()

        return [c for c in contents if c]

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

    async def get_book_node_list(self, user_id:int, bid:str, correlation: list[int])->List[BookNode]:
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
            bid=LZSDGenerator.generate_book_id(),  # 生成业务层书籍ID
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

        books = list(books)

        if not books:
            return books

        # 1️⃣ 收集所有 bid
        bids = [b.bid for b in books]

        # 2️⃣ 一次查所有 content
        content_map = await self.get_all_contents_grouped(bids)

        # 3️⃣ 计算字数
        for book in books:

            contents = content_map.get(book.bid, [])

            total = 0

            for content in contents:
                clean = strip_html_tags(content)
                total += len(clean)

            book.wordCount = total  # 直接覆盖

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
            book_len: int,
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
        if book_len:
            node.book_len = book_len

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
            content: str | None = None
    ) -> BookNode:
        """
        更新节点名称 / 正文
        """
        if name is not None:
            node.name = name
        if data is not None:
            node.data = data
        if content is not None:
            node.content = content

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
            category: BookNodeCategory,
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
            type=category.code
        )
        self.db.add(node)
        await self.db.flush()
        return node

    async def add_child_node(
            self,
            uid: int,
            bid: str,
            parent_node: BookNode,
            is_leaf: int,
            name: str,
            data: dict | None = None,
            content: str | None = None,
            category:BookNodeCategory = BookNodeCategory.NORMAL,
            order:int = 0,
    ) -> BookNode:
        """
        新增章节（自动补正文根节点）
        """
        _depth = 1
        _parent_id = 0
        _type = category.code
        if parent_node:
            _parent_id = parent_node.id
            _depth = parent_node.depth + 1
            _type = parent_node.type

        node = BookNode(
            bid=bid,
            uid=uid,
            parent_id=_parent_id,
            name=name,
            is_leaf=is_leaf,
            depth=_depth,
            data=data or {},
            content=content,
            type=_type,
            order=order,
        )
        self.db.add(node)
        await self.db.flush()
        return node

    async def batch_add_child_nodes(
            self,
            user_id: int,
            bid: str,
            parent_node: BookNode,
            chapter_data: list[Chapter],
            is_leaf:int,
    ):
        """
        批量添加子节点（章节）
        chapter_data 格式: [{"name": "标题", "content": "正文", "weight": 1}, ...]
        """
        if not chapter_data:
            return

        now = datetime.now()

        # 1. 构造批量数据
        # 根据你的模型，补全必须字段（depth, is_leaf, book_len 等）
        insert_values = [
            {
                "uid": user_id,
                "bid": bid,
                "parent_id": parent_node.id,
                "name": item.title,
                "content": item.content,
                "type": parent_node.type,  # 默认目录类型
                "is_leaf": is_leaf,
                "depth": parent_node.depth + 1,  # 假设内容根节点下是第 2 层
                "book_len": item.word_count,
                "data": {},
                "createTime": now,
                "updateTime": now
            }
            for item in chapter_data
        ]

        try:
            # 2. 执行批量插入
            # 使用 insert(Model) 的 values 列表模式，SQLAlchemy 会自动优化为批量 SQL
            stmt = insert(BookNode).values(insert_values)
            await self.db.execute(stmt)

            # 3. 注意：如果是异步环境，确保在此处或外部 commit
            # await self.db.commit()

        except Exception as e:
            logger.error(f"批量插入章节失败: {e}")
            raise e

    async def get_nodes_by_parent_ids(
        self,
        parent_ids: list[int],
    ) -> list[BookNode]:
        result = await self.db.execute(
            select(BookNode).where(BookNode.parent_id.in_(parent_ids))
        )
        nodes = result.scalars().all()
        return list(nodes)

    async def get_nodes_by_parent_id(
            self,
            bid: str,
            parent_id: int,
    ) -> list[BookNode]:
        result = await self.db.execute(
            select(BookNode).where(
                BookNode.parent_id == parent_id,
                BookNode.bid == bid
            )
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
            user_id:int
    ) -> Book | None:
        result = await self.db.execute(
            select(Book).where(Book.bid == bid, Book.uid == user_id)
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

    @staticmethod
    async def get_deconstruct_list_dao(
            db: AsyncSession,
            user_id: int,
            page: int,
            pageSize: int
    ):
        # =========================
        # 查询总数
        # =========================
        count_stmt = (
            select(func.count())
            .select_from(BookDeconstructRecord)
            .where(
                BookDeconstructRecord.userId == user_id,
                BookDeconstructRecord.isDelete == 0
            )
        )

        total_result = await db.execute(count_stmt)

        total = total_result.scalar() or 0

        # =========================
        # 查询分页数据
        # =========================
        stmt = (
            select(
                BookDeconstructRecord.id,
                BookDeconstructRecord.requestId,
                BookDeconstructRecord.title,
                BookDeconstructRecord.sourceUrl,
                BookDeconstructRecord.createdAt,

                AiNovelGenerateLog.status,
                AiNovelGenerateLog.errorMsg
            )
            .join(
                AiNovelGenerateLog,
                AiNovelGenerateLog.requestId == BookDeconstructRecord.requestId
            )
            .where(
                BookDeconstructRecord.userId == user_id,
                BookDeconstructRecord.isDelete == 0
            )
            .order_by(desc(BookDeconstructRecord.createdAt))
            .offset((page - 1) * pageSize)
            .limit(pageSize)
        )

        result = await db.execute(stmt)

        return result.all(), total