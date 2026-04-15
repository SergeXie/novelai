from typing import List, Dict, Set

from sqlalchemy import select

from core.entity.do.book_node import BookNode
from core.entity.do.books import Book


class BookExporter:
    def __init__(self, db_session):
        self.db = db_session

    async def export_to_markdown(self, book:Book, leaf_node_ids: List[int]) -> str:
        bid = book.bid
        user_id = book.uid
        book_info_nodes = [BookNode(
            bid=bid,
            depth=0,
            name="小说名称",
            content=book.title
        ), BookNode(
            bid=bid,
            depth=0,
            name="小说简介",
            content=book.description
        )]

        # 1. 获取所有相关的节点（包括叶子节点及其所有祖先）
        all_related_nodes = await self._get_full_tree_context(bid, leaf_node_ids)

        if not all_related_nodes:
            return ""

        basic_prompt = self._render_nodes(nodes=book_info_nodes, tree_map=None)

        # 2. 将节点组织成父子结构字典 {parent_id: [children]}
        tree_map: Dict[int, List[BookNode]] = {}
        root_nodes: List[BookNode] = []

        # 排序确保同级节点按创建时间或ID顺序排列
        all_related_nodes.sort(key=lambda x: (x.depth, x.id))

        for node in all_related_nodes:
            if node.parent_id is None or node.parent_id == 0:
                root_nodes.append(node)
            else:
                if node.parent_id not in tree_map:
                    tree_map[node.parent_id] = []
                tree_map[node.parent_id].append(node)

        # 3. 递归构建 Markdown 内容
        return basic_prompt + "\n" + self._render_nodes(root_nodes, tree_map)

    async def _get_full_tree_context(self, bid: str, leaf_ids: List[int]) -> List[BookNode]:
        """递归追溯所有祖先节点并返回节点对象列表"""
        relevant_ids: Set[int] = set(leaf_ids)

        # 初始加载选中的叶子节点
        result = await self.db.execute(select(BookNode).where(BookNode.id.in_(leaf_ids)))
        nodes = list(result.scalars().all())

        # 向上追溯父节点
        current_batch = nodes
        while current_batch:
            parent_ids = {n.parent_id for n in current_batch if n.parent_id and n.parent_id not in relevant_ids}
            if not parent_ids:
                break

            res = await self.db.execute(select(BookNode).where(BookNode.id.in_(parent_ids)))
            parents = list(res.scalars().all())
            for p in parents:
                relevant_ids.add(p.id)
                nodes.append(p)
            current_batch = parents

        return nodes


    def _render_nodes(self, nodes: List[BookNode], tree_map: Dict[int, List[BookNode]] | None) -> str:
        """深度优先遍历生成 Markdown"""
        lines = []
        for node in nodes:
            # 根据 depth 生成标题 (depth=0 -> #, depth=1 -> ##)
            header_prefix = "#" * (node.depth + 1)
            lines.append(f"{header_prefix} {node.name}\n")

            # 如果节点有内容则写入（通常是叶子节点）
            if node.content:
                lines.append(f"{node.content}\n")

            # 如果有子节点，递归处理
            if tree_map and node.id in tree_map:
                # 递归子节点并添加到 lines
                child_content = self._render_nodes(tree_map[node.id], tree_map)
                lines.append(child_content)

        return "\n".join(lines)