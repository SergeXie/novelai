from typing import List, Any
from sqlalchemy.ext.asyncio import AsyncSession

from core.entity.do.book_node import BookNode
from core.entity.vo.boko_node_schema import NodeTreeSchema
from dao.book_dao import BookDAO


class BookService:
    def __init__(self, db: AsyncSession):
        self.book_dao = BookDAO(db)

    async def get_tree(self, bid:str) -> List[NodeTreeSchema]:
        tree = []
        # 从 DAO 获取原始数据库对象
        nodes = await self.book_dao.get_book_nodes(bid)

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