from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from common.exception.lzsd_exception import ServiceWarning
from common.utils.text_util import strip_html_tags
from core.entity.do.book_node import BookNode
from core.entity.do.books import Book
from core.entity.vo.book_node_schema import NodeTreeSchema
from core.entity.vo.bool_vo import Character
from core.enums.node_type import BookNodeCategory
from dao.book_dao import BookDAO
from dao.template_dao import TemplateDAO


class BookService:
    def __init__(self, db: AsyncSession):
        self.book_dao = BookDAO(db)
        self.db = db


    async def count_book_words(self,bid: str) -> int:
        """
        统计书籍字数（去HTML）
        """

        contents = await self.book_dao.get_contents_by_bid(bid)

        total = 0

        for content in contents:
            clean_text = strip_html_tags(content)
            total += len(clean_text)

        return total

    async def get_tree(self, bid:str, uid:int, max_depth:Optional[int] = None) -> List[NodeTreeSchema]:
        tree = []
        # 从 DAO 获取原始数据库对象
        nodes = await self.book_dao.get_book_nodes(bid, uid, max_depth)

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

    async def get_sub_tree(self, bid: str, uid: int, root_id: int) -> List[NodeTreeSchema]:
        """
        获取指定 root_id 节点及其所有子孙构成的树
        """
        # 1. 依然获取该书的所有节点（构建完整的 map 关系）
        # 注意：如果节点数巨大，建议在 DAO 层加 defer(BookNode.content)
        full_tree = await self.get_tree(bid, uid)

        # 2. 我们需要一个平铺的 map 来快速定位 root_id
        # 如果 get_tree 内部没有返回 map，我们可以简单递归查找或在 get_tree 时保留 map
        def find_node_in_tree(nodes: List[NodeTreeSchema], target_id: int) -> Optional[NodeTreeSchema]:
            for node in nodes:
                if node.id == target_id:
                    return node
                if node.children:
                    found = find_node_in_tree(node.children, target_id)
                    if found:
                        return found
            return None

        target_node = find_node_in_tree(full_tree, root_id)

        # 3. 返回该节点及其子树（包装成列表格式）
        return [target_node] if target_node else []

    async def _create_nodes_from_template(self,
            uid:int,
            bid: str,
            nodes: list[dict],
            parent_id: int,
            depth: int,
    ):
        """
        递归创建模板节点
        """

        for item in nodes:
            # 1️⃣ 创建当前节点
            node = BookNode(
                bid=bid,
                uid=uid,
                parent_id=parent_id,
                name=item["title"],
                content=item.get("data"),
                is_leaf=item.get("is_leaf", 1),
                type=item.get("type", 0),
                depth=depth,
            )

            self.db.add(node)
            await self.db.flush()  # 拿到 node.id

            # 2️⃣ 如果有 children，递归创建
            children = item.get("children")
            if children:
                # 当前节点必须是非叶子
                node.is_leaf = 0

                await self._create_nodes_from_template(
                    uid=uid,
                    bid=bid,
                    nodes=children,
                    parent_id=node.id,
                    depth=depth + 1,
                )

    async def create_book_with_tree(
            self,
            uid: int,
            title: str,
            description: str | None,
            template_id: str
    ) -> Book:
        """
        创建书籍 + 初始化标准树结构
        """
        # 2️ 查询模板
        template = await TemplateDAO.get_template_by_template_id(
            self.db,
            template_id,
        )

        print("user:{} create book:{} tpl:{}".format(uid, title, template.tpl_name))

        # 1️ 创建书籍
        book = await self.book_dao.create_book(
            uid=uid,
            title=title,
            bookType=template.tpl_name,
            description=description,
            template_id=template_id
        )

        template_data = template.data  # JSON

        # 3️⃣ 递归创建节点（root parent_id = 0）
        await self._create_nodes_from_template(
            uid=uid,
            bid=book.bid,
            nodes=template_data,
            parent_id=0,
            depth=0,
        )

        # 2 统一提交
        await self.db.commit()
        await self.db.refresh(book)

        return book

    async def edit_book(
            self,
            template_id: str,
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
        book = await self.book_dao.get_book_by_bid(bid, uid)
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

        values["template_id"] = template_id
        # 3️ 更新
        await self.book_dao.update_book(
            bid=bid,
            uid=uid,
            values=values,
        )
        # 4 返回最新书籍信息
        return await self.book_dao.get_book_by_bid(bid, uid)

    async def list_books(
            self,
            *,
            status: int | None = None,
            uid:int
    ) -> list[Book]:
        """
        获取用户书籍列表
        """

        return await self.book_dao.list_books(
            uid=uid,
            status=status,
        )

    async def get_book_node_detail(
            self,
            node_id: int,
            uid: int,
            bid: str,
    ) -> BookNode:
        """
        获取书籍节点详情
        """
        node = await self.book_dao.get_node_by_id(
            node_id=node_id,
            uid=uid,
            bid=bid,
        )

        if not node:
            # 你项目里如果有自定义异常，这里可以替换
            raise ServiceWarning(message='书籍节点不存在')

        return node

    async def update_book_node_content(
            self,
            node_id: int,
            uid: int,
            bid: str,
            book_len: int,
            content: str | None,
            data: dict | None = None,
    ) -> BookNode:
        """
        编辑书籍节点内容
        """
        node = await self.book_dao.get_node_by_id(
            node_id=node_id,
            uid=uid,
            bid=bid
        )

        if not node:
            raise ServiceWarning("书籍节点不存在")

        return await self.book_dao.update_node_content(
            node=node,
            book_len=book_len,
            content=content,
            data=data,
        )

    async def edit_book_node(
            self,
            node_id: int,
            uid: int,
            bid: str,
            name: str | None,
            data: dict | None = None,
    ) -> BookNode:
        """
        编辑章节 / 节点
        """
        node = await self.book_dao.get_node_by_id(node_id=node_id, uid=uid, bid=bid)

        if not node:
            raise ServiceWarning("节点不存在")

        return await self.book_dao.update_node(
            node,
            name=name,
            data=data
        )

    async def add_chapter(
            self,
            uid: int,
            bid: str,
            parent_id: int,
            is_leaf: int,
            name: str,
            type: int,
            data: dict | None = None,
            content: str | None = None
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
            parent = await self.book_dao.get_node_parent_by_id(parent_id=parent_id, uid=uid, bid=bid)
            if not parent:
                raise ServiceWarning("父节点不存在")
            if parent.bid != bid:
                raise ServiceWarning("父节点不属于该书籍")

            parent_depth = parent.depth

        # 3️⃣ 创建章节节点
        node = await self.book_dao.add_chapter_node(
            uid=uid,
            bid=bid,
            parent_id=parent_id,
            is_leaf=1 if is_leaf else 0,
            name=name,
            depth=parent_depth + 1,
            data=data,
            content=content,
            type=type if type else parent.type
        )

        # 3️⃣ 父节点修正（核心规则）
        if parent and parent.is_leaf == 1:
            parent.is_leaf = 0
            self.db.add(parent)

        # 5️⃣ 提交
        await self.db.commit()
        await self.db.refresh(node)

        return node


    async def delete_node_(
            self,
            bid: str,
            node_id: int,
            uid:int
    ):
        """
        删除节点（包含整个子树）
        """

        # 1️⃣ 校验目标节点
        node = await self.book_dao.get_node_by_id(node_id=node_id, uid=uid, bid=bid)
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

            children = await self.book_dao.get_nodes_by_parent_ids([current_id])
            queue.extend([c.id for c in children])

        # 3️⃣ 执行删除
        await self.book_dao.delete_nodes(uid=uid, bid=bid, node_ids=to_delete_ids)

        # 4️⃣ 回滚父节点 is_leaf
        # if parent_id != 0:
        #     siblings = await self.book_dao.get_nodes_by_parent_ids(
        #         [parent_id]
        #     )
        #     if not siblings:
        #         parent = await self.book_dao.get_node_by_id(node_id=parent_id, uid=uid, bid=bid)
        #         if parent:
        #             parent.is_leaf = 1
        #             db.add(parent)

        return {
            "deleted_ids": to_delete_ids
        }

    async def offline_book(
            self,
            bid: str,
            uid: int
    ):
        """
        下架书籍（逻辑删除）
        """

        # 1️ 校验书籍
        book = await self.book_dao.get_book_by_bid(bid, uid)
        if not book:
            raise ServiceWarning("书籍不存在")

        if book.uid != uid:
            raise ServiceWarning("无权限操作该书籍")

        if book.status == 3:
            # 已下架，幂等
            return {"bid": bid, "status": 3}

        # 2️ 更新状态为下架
        await self.book_dao.update_book_status(
            bid=bid,
            status=3,
        )

        return {
            "bid": bid,
            "status": 3,
        }

    async def hard_delete_book(
            self,
            bid: str,
            uid: int,
    ):
        """
        真正删除书籍（物理删除）
        """

        # 1️ 校验书籍存在
        book = await self.book_dao.get_book_by_bid(bid, uid)
        if not book:
            raise ServiceWarning("书籍不存在")

        if book.uid != uid:
            raise ServiceWarning("无权限操作该书籍")

        # ️ 2 必须已下架才能物理删除
        if book.status != 3:
            raise ServiceWarning("请先下架书籍后再删除")

        # 3️ 删除节点
        await self.book_dao.delete_nodes_by_bid(bid, uid)

        # 4 删除书籍
        await self.book_dao.hard_delete_book(bid, uid)

        return {
            "bid": bid,
            "deleted": True
        }

    async def auto_create_book(self, user_id:int, title:str, summary:str, roles:List[Character])->Book:
        book = await self.create_book_with_tree(
            title=title,
            description=summary,
            uid=user_id,
            template_id="TPLXIAOSHUO",
        )

        if book:
            nodes = await self.book_dao.get_book_nodes(bid=book.bid, user_id=user_id, max_depth=1)
            node:BookNode = None
            for node in nodes:
                if node.type == BookNodeCategory.ROLES.code:
                    for role in roles:
                        await self.book_dao.add_child_node(bid=book.bid, uid=user_id, parent_node=node, is_leaf=1, name=role.name, content=role.role)

        return book

