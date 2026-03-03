from typing import List, Any
from sqlalchemy.ext.asyncio import AsyncSession

from common.exception.lzsd_exception import ServiceWarning
from core.entity.do.book_node import BookNode
from core.entity.do.books import Book
from core.entity.vo.boko_node_schema import NodeTreeSchema
from dao.book_dao import BookDAO


class BookService:
    def __init__(self, db: AsyncSession):
        self.book_dao = BookDAO(db)

    async def get_tree(self, bid:str, uid:int) -> List[NodeTreeSchema]:
        tree = []
        # 从 DAO 获取原始数据库对象
        nodes = await self.book_dao.get_book_nodes(bid, uid)

        if nodes:
            # 1. 转换原始数据库对象为模型对象
            node_map = {}
            for node in nodes:
                # 验证并转换
                node_obj = NodeTreeSchema.model_validate(node)
                # 手动初始化 children 为独立的空列表，确保不是 None
                node_obj.children = []
                node_map[node.id] = node_obj

            # 2. 构建层级
            for node in node_map.values():
                if node.parent_id is None:
                    # 顶级节点
                    tree.append(node)
                else:
                    parent = node_map.get(node.parent_id)
                    if parent:
                        # 此时 parent.children 已经是 []，可以安全地 append
                        parent.children.append(node)
                    else:
                        # 容错：找不到父节点的（孤儿节点）归为根节点
                        tree.append(node)

        # 按照 id 或自定义排序字段进行排序（可选）
        # tree.sort(key=lambda x: x.id)

        return tree

    @staticmethod
    async def create_book(
            db: AsyncSession,
            *,
            title: str,
            bookType: str,
            description: str | None,
            uid:int
    ) -> Book:
        """
        创建书籍业务逻辑
        目前仅包装 DAO，后续可加：
        - 自动创建 mc_book_node 根节点
        - 风控校验
        """

        return await BookDAO.create_book(
            db,
            uid=uid,
            title=title,
            bookType=bookType,
            description=description,
        )

    @staticmethod
    async def create_book_with_tree(
            db: AsyncSession,
            *,
            uid: int,
            title: str,
            bookType: str,
            description: str | None,
    ) -> Book:
        """
        创建书籍 + 初始化标准树结构
        """
        # 1️ 创建书籍
        book = await BookDAO.create_book(
            db,
            uid=uid,
            title=title,
            bookType=bookType,
            description=description,
        )

        # 2 统一提交
        await db.commit()
        await db.refresh(book)

        return book

    @staticmethod
    async def edit_book(
            db: AsyncSession,
            *,
            bid: str,
            uid: int,
            title: str | None,
            bookType: str | None,
            description: str | None,
    ):
        """
        编辑书籍信息
        """

        # 1️⃣ 校验书籍存在
        book = await BookDAO.get_book_by_bid(db, bid, uid)
        if not book:
            raise ServiceWarning("书籍不存在")

        if book.uid != uid:
            raise ServiceWarning("无权限编辑该书籍")

        # 2️⃣ 组装更新字段
        values = {}

        if title is not None:
            values["title"] = title

        if bookType is not None:
            values["bookType"] = bookType

        if description is not None:
            values["description"] = description

        # 3️ 更新
        await BookDAO.update_book(
            db,
            bid=bid,
            uid=uid,
            values=values,
        )

        await db.commit()

        # 4 返回最新书籍信息
        return await BookDAO.get_book_by_bid(db, bid, uid)

    @staticmethod
    async def list_books(
            db: AsyncSession,
            *,
            status: int | None = None,
            uid:int
    ) -> list[Book]:
        """
        获取用户书籍列表
        """

        return await BookDAO.list_books(
            db,
            uid=uid,
            status=status,
        )

    @staticmethod
    async def get_book_node_detail(
            db: AsyncSession,
            *,
            node_id: int,
            uid: int,
            bid: str,
    ) -> BookNode:
        """
        获取书籍节点详情
        """
        node = await BookDAO.get_node_by_id(
            db,
            node_id=node_id,
            uid=uid,
            bid=bid,
        )

        if not node:
            # 你项目里如果有自定义异常，这里可以替换
            raise ServiceWarning(message='书籍节点不存在')

        return node


    @staticmethod
    async def update_book_node_content(
        db: AsyncSession,
        *,
        node_id: int,
        uid: int,
        bid: str,
        content: str | None,
    ) -> BookNode:
        """
        编辑书籍节点内容
        """
        node = await BookDAO.get_node_by_id(
            db,
            node_id=node_id,
            uid=uid,
            bid=bid

        )

        if not node:
            raise ServiceWarning("书籍节点不存在")

        return await BookDAO.update_node_content(
            db,
            node=node,
            content=content,
        )

    @staticmethod
    async def edit_book_node(
            db: AsyncSession,
            *,
            node_id: int,
            uid: int,
            bid: str,
            name: str | None,
    ) -> BookNode:
        """
        编辑章节 / 节点
        """
        node = await BookDAO.get_node_by_id(db, node_id=node_id, uid=uid, bid=bid)

        if not node:
            raise ServiceWarning("节点不存在")

        return await BookDAO.update_node(
            db,
            node,
            name=name,
        )

    @staticmethod
    async def add_chapter(
            db: AsyncSession,
            *,
            uid: int,
            bid: str,
            parent_id: int,
            is_leaf: int,
            name: str,
    ) -> BookNode:
        """
        新增章节（业务接口）
        """

        # 1️⃣ 处理 root / 非 root
        if parent_id == 0:
            parent = None
            parent_depth = 0
        else:
            # 1️⃣ 校验节点
            parent = await BookDAO.get_node_parent_by_id(db, parent_id=parent_id, uid=uid, bid=bid)
            print(parent.uid)
            print(parent.parent_id)
            print(parent.name)
            if not parent:
                raise ServiceWarning("父节点不存在")
            if parent.bid != bid:
                raise ServiceWarning("父节点不属于该书籍")

            parent_depth = parent.depth

        # 3️⃣ 创建章节节点
        node = await BookDAO.add_chapter_node(
            db,
            uid=uid,
            bid=bid,
            parent_id=parent_id,
            is_leaf=1 if is_leaf else 0,
            name=name,
            depth=parent_depth + 1,
        )

        # 3️⃣ 父节点修正（核心规则）
        if parent and parent.is_leaf == 1:
            parent.is_leaf = 0
            db.add(parent)

        # 5️⃣ 提交
        await db.commit()
        await db.refresh(node)

        return node

    @staticmethod
    async def delete_node_(
            db: AsyncSession,
            *,
            bid: str,
            node_id: int,
            uid:int
    ):
        """
        删除节点（包含整个子树）
        """

        # 1️⃣ 校验目标节点
        node = await BookDAO.get_node_by_id(db, node_id=node_id, uid=uid, bid=bid)
        if not node:
            raise ServiceWarning("节点不存在")

        if node.bid != bid:
            raise ServiceWarning("节点不属于该书籍")

        parent_id = node.parent_id

        # 2️⃣ 收集整棵子树（BFS）
        to_delete_ids = []
        queue = [node_id]

        while queue:
            current_id = queue.pop(0)
            to_delete_ids.append(current_id)

            children = await BookDAO.get_nodes_by_parent_ids(
                db, [current_id]
            )
            queue.extend([c.id for c in children])

        # 3️⃣ 执行删除
        await BookDAO.delete_nodes(db, to_delete_ids)

        # 4️⃣ 回滚父节点 is_leaf
        # if parent_id != 0:
        #     siblings = await BookDAO.get_nodes_by_parent_ids(
        #         db, [parent_id]
        #     )
        #     if not siblings:
        #         parent = await BookDAO.get_node_by_id(db, node_id=parent_id, uid=uid, bid=bid)
        #         if parent:
        #             parent.is_leaf = 1
        #             db.add(parent)

        # 5️⃣ 提交事务
        await db.commit()

        return {
            "deleted_ids": to_delete_ids
        }

    @staticmethod
    async def offline_book(
            db: AsyncSession,
            *,
            bid: str,
            uid: int
    ):
        """
        下架书籍（逻辑删除）
        """

        # 1️⃣ 校验书籍
        book = await BookDAO.get_book_by_bid(db, bid, uid)
        if not book:
            raise ServiceWarning("书籍不存在")

        if book.uid != uid:
            raise ServiceWarning("无权限操作该书籍")

        if book.status == 3:
            # 已下架，幂等
            return {"bid": bid, "status": 3}

        # 2️⃣ 更新状态为下架
        await BookDAO.update_book_status(
            db,
            bid=bid,
            status=3,
        )

        await db.commit()

        return {
            "bid": bid,
            "status": 3,
        }
