import io
import os
from datetime import datetime
from html.parser import HTMLParser
from types import SimpleNamespace
from typing import List, Optional
from urllib.parse import urlparse, unquote
import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from common.exception.errors import ServerError, NotFoundError, RequestError
from common.exception.lzsd_exception import ServiceWarning
from common.modules.html_text_extractor import quick_html_to_text
from common.utils.text_util import strip_html_tags
from core.entity.do.book_deconstruct_record_do import BookDeconstructRecord
from core.entity.do.book_node import BookNode
from core.entity.do.books import Book
from core.entity.vo.base_vo import PageResp
from core.entity.vo.book_node_schema import BookSearchChapterItem, BookSearchResp, BookSearchSnippetItem, NodeTreeSchema
from core.entity.vo.bool_vo import Character, ChapterData
from core.entity.vo.generate_log_vo import BookDeconstructItemVO
from core.enums.node_type import BookNodeCategory
from core.processor.book_processor import Chapter
from dao.book_dao import BookDAO
from dao.template_dao import TemplateDAO

DEFAULT_TEMPLATE_ID = "TPLXIAOSHUO"

# 系统固定节点使用负数 ID，避免和 mc_book_node.id 的自增正数冲突。
# 这些节点只在 /book/tree 响应里返回，不写入 mc_book_node 表。
BOOK_SYSTEM_BASIC_ID = -1
BOOK_SYSTEM_ROLES_ID = -2
BOOK_SYSTEM_WORLDVIEW_ID = -3
BOOK_SYSTEM_WRITING_STYLE_ID = -4
BOOK_SYSTEM_OUTLINE_ID = -5
BOOK_SYSTEM_CONTENT_ID = -6
BOOK_SYSTEM_DETAILED_OUTLINE_ID = -7

BOOK_SYSTEM_NODES = [
    {
        "id": BOOK_SYSTEM_BASIC_ID,
        "name": "基础设定",
        "parent_id": 0,
        "is_leaf": 0,
        "type": BookNodeCategory.NORMAL.code,
        "depth": 0,
        "children": [
            {
                "id": BOOK_SYSTEM_ROLES_ID,
                "name": "角色",
                "parent_id": BOOK_SYSTEM_BASIC_ID,
                "is_leaf": 0,
                "type": BookNodeCategory.ROLES.code,
                "depth": 1,
            },
            {
                "id": BOOK_SYSTEM_WORLDVIEW_ID,
                "name": "世界观",
                "parent_id": BOOK_SYSTEM_BASIC_ID,
                "is_leaf": 0,
                "type": BookNodeCategory.WORLDVIEW.code,
                "depth": 1,
            },
            {
                "id": BOOK_SYSTEM_WRITING_STYLE_ID,
                "name": "写作要求",
                "parent_id": BOOK_SYSTEM_BASIC_ID,
                "is_leaf": 1,
                "type": BookNodeCategory.WRITING_STYLE.code,
                "depth": 1,
            },
            {
                "id": BOOK_SYSTEM_OUTLINE_ID,
                "name": "大纲",
                "parent_id": BOOK_SYSTEM_BASIC_ID,
                "is_leaf": 0,
                "type": BookNodeCategory.OUTLINE.code,
                "depth": 1,
            },
            {
                "id": BOOK_SYSTEM_DETAILED_OUTLINE_ID,
                "name": "细纲",
                "parent_id": BOOK_SYSTEM_BASIC_ID,
                "is_leaf": 0,
                "type": BookNodeCategory.DETAILED_OUTLINE.code,
                "depth": 1,
            },
        ],
    },
    {
        "id": BOOK_SYSTEM_CONTENT_ID,
        "name": "正文",
        "parent_id": 0,
        "is_leaf": 0,
        "type": BookNodeCategory.CONTENT.code,
        "depth": 0,
    },
]

# 快速查询表：真实用户节点挂到虚拟父节点下时，用它拿 depth/type。
BOOK_SYSTEM_NODE_DEPTH = {
    item["id"]: item["depth"]
    for root in BOOK_SYSTEM_NODES
    for item in [root, *root.get("children", [])]
}
BOOK_SYSTEM_NODE_TYPE = {
    item["id"]: item["type"]
    for root in BOOK_SYSTEM_NODES
    for item in [root, *root.get("children", [])]
}
BOOK_SYSTEM_NODE_NAME = {
    item["id"]: item["name"]
    for root in BOOK_SYSTEM_NODES
    for item in [root, *root.get("children", [])]
}
BOOK_SYSTEM_NODE_PARENT = {
    item["id"]: item["parent_id"]
    for root in BOOK_SYSTEM_NODES
    for item in [root, *root.get("children", [])]
}
BOOK_SYSTEM_NODE_IS_LEAF = {
    item["id"]: item["is_leaf"]
    for root in BOOK_SYSTEM_NODES
    for item in [root, *root.get("children", [])]
}
BOOK_SYSTEM_NODE_IDS = set(BOOK_SYSTEM_NODE_DEPTH)
LEGACY_BASIC_CHILD_TYPE_TO_SYSTEM_ID = {
    BookNodeCategory.ROLES.code: BOOK_SYSTEM_ROLES_ID,
    BookNodeCategory.WORLDVIEW.code: BOOK_SYSTEM_WORLDVIEW_ID,
    BookNodeCategory.WRITING_STYLE.code: BOOK_SYSTEM_WRITING_STYLE_ID,
    BookNodeCategory.OUTLINE.code: BOOK_SYSTEM_OUTLINE_ID,
    BookNodeCategory.DETAILED_OUTLINE.code: BOOK_SYSTEM_DETAILED_OUTLINE_ID,
}


class SearchBlockTextParser(HTMLParser):
    BLOCK_TAGS = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self):
        super().__init__()
        self.blocks: list[str] = []
        self._tag_stack: list[str] = []
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        if tag.lower() in self.BLOCK_TAGS:
            if not self._tag_stack:
                self._buffer = []
            self._tag_stack.append(tag.lower())

    def handle_data(self, data: str):
        if self._tag_stack:
            self._buffer.append(data)

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag not in self.BLOCK_TAGS or tag not in self._tag_stack:
            return

        while self._tag_stack:
            current = self._tag_stack.pop()
            if current == tag:
                break

        if not self._tag_stack:
            text = " ".join("".join(self._buffer).split())
            if text:
                self.blocks.append(text)
            self._buffer = []


class BookService:
    def __init__(self, db: AsyncSession):
        self.book_dao = BookDAO(db)
        self.db = db

    @staticmethod
    def normalize_cover_path(cover_url: str | None) -> str | None:
        """Store only the cover resource path, e.g. http://host/files/a.jpg -> /files/a.jpg."""
        if cover_url is None:
            return None

        cover_url = cover_url.strip()
        if not cover_url:
            return ""

        parsed_url = urlparse(cover_url)
        cover_path = parsed_url.path if parsed_url.scheme and parsed_url.netloc else cover_url
        cover_path = cover_path.strip()

        if not cover_path:
            raise ServiceWarning("封面地址无效")

        if not cover_path.startswith("/"):
            cover_path = f"/{cover_path}"

        if len(cover_path) > 512:
            raise ServiceWarning("封面地址不能超过512个字符")

        return cover_path

    @staticmethod
    async def extract_book_title(url: str) -> str:
        """
        从 txt url 提取书名
        """

        # 解析 path
        path = urlparse(url).path

        # 获取文件名
        filename = os.path.basename(path)

        # URL 解码
        filename = unquote(filename)

        # 去掉扩展名
        title = os.path.splitext(filename)[0]

        return title

    async def get_book_by_bid(self, bid: str, user_id: int) -> Optional[Book]:
        if bid:
            return await self.book_dao.get_book_by_bid(bid=bid, user_id=user_id)
        return None

    async def get_tree(self, bid: str, uid: int, max_depth: Optional[int] = None) -> List[NodeTreeSchema]:
        # 先构建代码固定的系统树，再把数据库里的真实节点挂到对应位置。
        tree = self._build_system_tree(bid=bid, uid=uid, max_depth=max_depth)
        system_node_map: dict[int, NodeTreeSchema] = {}
        self._collect_tree_nodes(tree, system_node_map)

        nodes = await self.book_dao.get_book_nodes(bid, uid, max_depth)

        if nodes:
            # 旧书可能已经把基础设定/角色/正文等系统节点写入了数据库。
            # 这里不改库，只在响应里隐藏旧系统节点，并把它们的子节点映射到新的虚拟 ID 下。
            legacy_system_parent_map = self._build_legacy_system_parent_map(nodes)
            legacy_system_node_ids = set(legacy_system_parent_map)

            node_map = {}
            for node in nodes:
                if node.id in legacy_system_node_ids:
                    continue

                node_obj = NodeTreeSchema.model_validate(node)
                node_obj.children = []
                # 如果真实节点挂在旧的入库系统节点下，响应时移动到对应虚拟父节点下。
                node_obj.parent_id = legacy_system_parent_map.get(node.parent_id, node.parent_id)
                node_map[node.id] = node_obj

            for node in node_map.values():
                if node.parent_id in system_node_map:
                    # 新数据可以直接使用 parent_id=-2/-6，旧数据经过映射后也会走到这里。
                    system_node_map[node.parent_id].children.append(node)
                elif node.parent_id is None or node.parent_id == 0:
                    tree.append(node)
                else:
                    parent = node_map.get(node.parent_id)
                    if parent:
                        parent.children.append(node)
                    else:
                        tree.append(node)

        return tree

    @staticmethod
    def _build_system_tree(bid: str, uid: int, max_depth: Optional[int]) -> List[NodeTreeSchema]:
        # 把 BOOK_SYSTEM_NODES 字典转换成和数据库节点一致的返回结构。
        # 这里也处理 max_depth，保证虚拟节点同样遵守 /book/tree 的层级过滤。
        def build_node(item: dict) -> NodeTreeSchema | None:
            if max_depth is not None and item["depth"] > max_depth:
                return None

            node = NodeTreeSchema(
                id=item["id"],
                bid=bid,
                uid=uid,
                name=item["name"],
                parent_id=item["parent_id"],
                is_leaf=item["is_leaf"],
                type=item["type"],
                book_len=0,
                data={"system_key": item["id"]},
                children=[],
            )

            for child in item.get("children", []):
                child_node = build_node(child)
                if child_node:
                    node.children.append(child_node)
            return node

        return [node for item in BOOK_SYSTEM_NODES if (node := build_node(item))]

    @staticmethod
    def _collect_tree_nodes(nodes: List[NodeTreeSchema], node_map: dict[int, NodeTreeSchema]) -> None:
        # 把虚拟树拍平成 map，方便后面按 parent_id 快速挂载真实节点。
        for node in nodes:
            node_map[node.id] = node
            if node.children:
                BookService._collect_tree_nodes(node.children, node_map)

    @staticmethod
    def _build_legacy_system_parent_map(nodes: List[BookNode]) -> dict[int, int]:
        """把旧的入库系统节点映射到新的虚拟 ID，不修改数据库数据。"""
        legacy_map: dict[int, int] = {}

        # New books persist edited virtual-node content in a hidden backing node.
        # system_key keeps the public negative ID stable while the database uses
        # its own positive primary key.
        for node in nodes:
            system_key = node.data.get("system_key") if isinstance(node.data, dict) else None
            if system_key in BOOK_SYSTEM_NODE_IDS:
                legacy_map[node.id] = system_key

        root_nodes = [node for node in nodes if node.parent_id in (None, 0)]
        # 旧模板里的“基础设定”根节点通常是 type=0，且没有正文内容。
        legacy_basic_ids = [
            node.id
            for node in root_nodes
            if node.type == BookNodeCategory.NORMAL.code and not node.content
        ]

        for node_id in legacy_basic_ids:
            legacy_map[node_id] = BOOK_SYSTEM_BASIC_ID

        for node in root_nodes:
            # 旧模板里的“正文”根节点通常是 type=1，且没有正文内容。
            if node.type == BookNodeCategory.CONTENT.code and not node.content:
                legacy_map[node.id] = BOOK_SYSTEM_CONTENT_ID

        for node in nodes:
            # “基础设定”下面的旧子节点按类型映射：
            # 角色/世界观/写作要求/大纲 -> -2/-3/-4/-5。
            if node.parent_id in legacy_basic_ids and node.type in LEGACY_BASIC_CHILD_TYPE_TO_SYSTEM_ID:
                legacy_map[node.id] = LEGACY_BASIC_CHILD_TYPE_TO_SYSTEM_ID[node.type]

        return legacy_map

    @staticmethod
    def _pick_virtual_backing_node(
            nodes: List[BookNode],
            legacy_system_parent_map: dict[int, int],
            node_id: int,
    ) -> BookNode | None:
        mapped_nodes = [
            node for node in nodes
            if legacy_system_parent_map.get(node.id) == node_id
        ]
        if mapped_nodes:
            return next((node for node in mapped_nodes if node.content), mapped_nodes[0])

        # 写作要求已经完成数据迁移，只通过 data.system_key=-4 识别承载记录，
        # 不再按 type=4 猜测，避免误读同类型的普通节点。
        if node_id == BOOK_SYSTEM_WRITING_STYLE_ID:
            return None

        # 其他系统节点暂时保留旧数据兼容：旧父节点被删除后，按节点类型找回内容。
        system_type = BOOK_SYSTEM_NODE_TYPE.get(node_id)
        if system_type is None:
            return None

        candidates = [
            node for node in nodes
            if node.type == system_type and (node.content or node.data)
        ]
        if not candidates:
            return None

        return next((node for node in candidates if node.content), candidates[0])

    async def get_basic_nodes(self, bid: str, user_id: int) -> List[BookNode]:
        nodes = await self.book_dao.get_book_nodes(bid=bid, user_id=user_id) or []
        # 核心逻辑：保留 is_leaf 等于 1 且 type 大于 1 的元素
        return [node for node in nodes if node.is_leaf == 1 and node.type > 1]

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

    async def create_book_with_tree(
            self,
            uid: int,
            title: str,
            description: str | None,
            template_id: str,
            coverUrl: str | None = None,
    ) -> Book:
        """
        创建书籍 + 初始化标准树结构
        """
        # 2️ 查询模板
        template = await TemplateDAO.get_template_by_template_id(self.db, template_id, )

        # 1️ 创建书籍
        book = await self.book_dao.create_book(
            uid=uid,
            title=title,
            bookType=template.tpl_name,
            description=description,
            template_id=template_id,
            coverUrl=self.normalize_cover_path(coverUrl),
        )

        # 3️⃣ 递归创建节点（root parent_id = 0）
        # System nodes are now virtual and are not stored in mc_book_node.

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
            coverUrl: str | None = None,
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

        if coverUrl is not None:
            values["coverUrl"] = self.normalize_cover_path(coverUrl)

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
            uid: int
    ) -> list[Book]:
        """
        获取用户书籍列表
        """

        return await self.book_dao.list_books(
            uid=uid,
            status=status,
        )

    async def search_book_content(
            self,
            uid: int,
            bid: str,
            keyword: str,
            limit: int | None = None,
            snippet_size: int = 24,
            max_snippets_per_node: int | None = None,
    ) -> BookSearchResp:
        keyword = (keyword or "").strip()
        if not keyword:
            raise ServiceWarning("搜索关键词不能为空")

        book = await self.book_dao.get_book_by_bid(bid=bid, user_id=uid)
        if not book:
            raise ServiceWarning("书籍不存在")

        nodes = await self.book_dao.search_content_nodes(
            user_id=uid,
            bid=bid,
            keyword=keyword,
            limit=limit,
        )

        items: list[BookSearchChapterItem] = []
        total = 0
        for node in nodes:
            snippets, match_count = self._build_node_search_snippets(
                content=node.content or "",
                keyword=keyword,
                snippet_size=snippet_size,
                max_snippets=max_snippets_per_node,
            )
            if match_count <= 0:
                continue

            total += match_count

            items.append(
                BookSearchChapterItem(
                    nodeId=node.id,
                    chapterName=node.name,
                    matchCount=match_count,
                    snippets=[BookSearchSnippetItem(snippet=snippet) for snippet in snippets],
                )
            )

        return BookSearchResp(keyword=keyword, total=total, list=items)

    @classmethod
    def _build_node_search_snippets(
            cls,
            *,
            content: str,
            keyword: str,
            snippet_size: int,
            max_snippets: int | None,
    ) -> tuple[list[str], int]:
        blocks = cls._extract_search_blocks(content)
        if blocks:
            snippets: list[str] = []
            match_count = 0
            for block in blocks:
                positions = cls._find_keyword_positions(block, keyword)
                if not positions:
                    continue

                match_count += len(positions)
                snippets.append(block)

            if max_snippets is not None:
                snippets = snippets[:max_snippets]

            return snippets, match_count

        clean_content = " ".join(strip_html_tags(content).split())
        positions = cls._find_keyword_positions(clean_content, keyword)
        return cls._build_search_snippets(
            text=clean_content,
            keyword=keyword,
            positions=positions,
            snippet_size=snippet_size,
            max_snippets=max_snippets,
        ), len(positions)

    @staticmethod
    def _extract_search_blocks(content: str) -> list[str]:
        parser = SearchBlockTextParser()
        parser.feed(content or "")
        parser.close()
        return parser.blocks

    @staticmethod
    def _find_keyword_positions(text: str, keyword: str) -> list[int]:
        if not text or not keyword:
            return []

        positions: list[int] = []
        haystack = text.lower()
        needle = keyword.lower()
        start = 0
        while True:
            index = haystack.find(needle, start)
            if index < 0:
                break
            positions.append(index)
            start = index + len(needle)
        return positions

    @staticmethod
    def _build_search_snippets(
            *,
            text: str,
            keyword: str,
            positions: list[int],
            snippet_size: int,
            max_snippets: int | None,
    ) -> list[str]:
        snippets: list[str] = []
        keyword_len = len(keyword)
        target_positions = positions if max_snippets is None else positions[:max_snippets]
        for position in target_positions:
            start = max(position - snippet_size, 0)
            end = min(position + keyword_len + snippet_size, len(text))
            snippets.append(text[start:end])
        return snippets

    async def get_book_node_detail(
            self,
            node_id: int,
            uid: int,
            bid: str,
    ) -> BookNode | SimpleNamespace:
        """
        获取书籍节点详情
        """
        if node_id in BOOK_SYSTEM_NODE_IDS:
            return await self._get_virtual_node_detail(
                node_id=node_id,
                uid=uid,
                bid=bid,
            )

        node = await self.book_dao.get_node_by_id(
            node_id=node_id,
            uid=uid,
            bid=bid,
        )

        if not node:
            # 你项目里如果有自定义异常，这里可以替换
            raise ServiceWarning(message='书籍节点不存在')

        return node

    async def _get_virtual_node_detail(
            self,
            node_id: int,
            uid: int,
            bid: str,
    ) -> SimpleNamespace:
        # 虚拟节点没有真实 mc_book_node.id。
        # 旧书如果曾经把系统节点入库，这里会找到对应旧节点，并复用它的 content/data 做详情回显。
        nodes = await self.book_dao.get_book_nodes(bid=bid, user_id=uid)
        legacy_system_parent_map = self._build_legacy_system_parent_map(nodes)
        legacy_node = self._pick_virtual_backing_node(
            nodes=nodes,
            legacy_system_parent_map=legacy_system_parent_map,
            node_id=node_id,
        )

        now = datetime.now()
        return SimpleNamespace(
            id=node_id,
            bid=bid,
            uid=uid,
            is_leaf=BOOK_SYSTEM_NODE_IS_LEAF[node_id],
            content=legacy_node.content if legacy_node else None,
            name=BOOK_SYSTEM_NODE_NAME[node_id],
            type=BOOK_SYSTEM_NODE_TYPE[node_id],
            depth=BOOK_SYSTEM_NODE_DEPTH[node_id],
            createTime=legacy_node.createTime if legacy_node else now,
            updateTime=legacy_node.updateTime if legacy_node else now,
            data=legacy_node.data if legacy_node and legacy_node.data else {"system_key": node_id},
        )

    async def update_book_node_content(
            self,
            node_id: int,
            uid: int,
            bid: str,
            book_len: int | None,
            content: str | None,
            data: dict | None = None,
    ) -> BookNode | SimpleNamespace:
        """
        编辑书籍节点内容
        """
        is_system_node = node_id in BOOK_SYSTEM_NODE_IDS
        if is_system_node:
            nodes = await self.book_dao.get_book_nodes(bid=bid, user_id=uid)
            legacy_system_parent_map = self._build_legacy_system_parent_map(nodes)
            node = self._pick_virtual_backing_node(
                nodes=nodes,
                legacy_system_parent_map=legacy_system_parent_map,
                node_id=node_id,
            )

            if node is None:
                node = await self.book_dao.add_chapter_node(
                    uid=uid,
                    bid=bid,
                    parent_id=BOOK_SYSTEM_NODE_PARENT[node_id],
                    is_leaf=BOOK_SYSTEM_NODE_IS_LEAF[node_id],
                    name=BOOK_SYSTEM_NODE_NAME[node_id],
                    depth=BOOK_SYSTEM_NODE_DEPTH[node_id],
                    data={"system_key": node_id},
                    category=BOOK_SYSTEM_NODE_TYPE[node_id],
                )
        else:
            node = await self.book_dao.get_node_by_id(
                node_id=node_id,
                uid=uid,
                bid=bid
            )

        if not node:
            raise ServiceWarning("书籍节点不存在")

        if is_system_node:
            system_data = dict(node.data or {})
            if data is not None:
                system_data.update(data)
            system_data["system_key"] = node_id
            data = system_data

        updated_node = await self.book_dao.update_node_content(
            node=node,
            book_len=book_len,
            content=content,
            data=data,
        )
        if is_system_node:
            return await self._get_virtual_node_detail(
                node_id=node_id,
                uid=uid,
                bid=bid,
            )
        return updated_node

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
        elif parent_id in BOOK_SYSTEM_NODE_IDS:
            # 虚拟父节点只存在于 BOOK_SYSTEM_NODES，不存在于数据库。
            # 所以这里不查父节点，直接使用配置里的 depth/type，并把新真实节点的 parent_id 写成负数。
            parent = None
            parent_depth = BOOK_SYSTEM_NODE_DEPTH[parent_id]
            if type is None:
                type = BOOK_SYSTEM_NODE_TYPE[parent_id]
            if parent_id == BOOK_SYSTEM_DETAILED_OUTLINE_ID:
                if type != BookNodeCategory.DETAILED_OUTLINE.code:
                    raise ServiceWarning("细纲子节点类型必须为细纲")
                if is_leaf != 1:
                    raise ServiceWarning("细纲目录下只能创建细纲叶子节点")
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
            category=type
        )

        # 3️⃣ 父节点修正（核心规则）
        if parent and parent.is_leaf == 1:
            parent.is_leaf = 0
            self.db.add(parent)

        # 5️⃣ 提交
        await self.db.commit()
        await self.db.refresh(node)

        return node

    async def bind_chapter_detail_outline(
            self,
            uid: int,
            bid: str,
            chapter_id: int,
            detail_outline_id: int | None,
    ) -> BookNode:
        """Bind a content chapter to a detailed-outline child node, or unbind it."""
        chapter = await self.book_dao.get_node_by_id(
            node_id=chapter_id,
            uid=uid,
            bid=bid,
        )
        if not chapter or chapter.type != BookNodeCategory.CONTENT.code:
            raise ServiceWarning("章节不存在或不是正文节点")

        if detail_outline_id == BOOK_SYSTEM_DETAILED_OUTLINE_ID:
            # The frontend submits the virtual "细纲" directory ID (-7). In that
            # case, create one real detailed-outline child for the current chapter.
            # A repeated request keeps the existing association and never creates a duplicate.
            if chapter.detail_outline_id is not None:
                existing_outline = await self.book_dao.get_node_by_id(
                    node_id=chapter.detail_outline_id,
                    uid=uid,
                    bid=bid,
                )
                if existing_outline:
                    return chapter

            detail_outline = await self.book_dao.add_chapter_node(
                uid=uid,
                bid=bid,
                parent_id=BOOK_SYSTEM_DETAILED_OUTLINE_ID,
                is_leaf=1,
                name=chapter.name,
                depth=BOOK_SYSTEM_NODE_DEPTH[BOOK_SYSTEM_DETAILED_OUTLINE_ID] + 1,
                data={"chapter_id": chapter.id},
                content=None,
                category=BookNodeCategory.DETAILED_OUTLINE,
            )
            detail_outline_id = detail_outline.id

        if detail_outline_id is not None:
            detail_outline = await self.book_dao.get_node_by_id(
                node_id=detail_outline_id,
                uid=uid,
                bid=bid,
            )
            if (
                not detail_outline
                or detail_outline.type != BookNodeCategory.DETAILED_OUTLINE.code
                or detail_outline.parent_id != BOOK_SYSTEM_DETAILED_OUTLINE_ID
            ):
                raise ServiceWarning("细纲不存在或不属于当前书籍")

            bound_chapter = await self.book_dao.get_chapter_by_detail_outline_id(
                bid=bid,
                uid=uid,
                detail_outline_id=detail_outline_id,
            )
            if bound_chapter and bound_chapter.id != chapter.id:
                raise ServiceWarning("该细纲已关联其他章节")

        return await self.book_dao.update_detail_outline_binding(
            chapter=chapter,
            detail_outline_id=detail_outline_id,
        )

    async def batch_add_roles(
            self,
            uid: int,
            items: list[dict],
    ) -> list[BookNode]:
        """在一次事务中批量新增角色节点。"""
        if not items:
            raise ServiceWarning("角色列表不能为空")

        try:
            # 批量接口允许一次提交多个角色，但每本书都必须属于当前用户。
            for bid in {item["bid"] for item in items}:
                if not await self.get_book_by_bid(bid=bid, user_id=uid):
                    raise ServiceWarning(f"书籍不存在或无权操作: {bid}")

            nodes = [
                BookNode(
                    uid=uid,
                    bid=item["bid"],
                    parent_id=BOOK_SYSTEM_ROLES_ID,
                    is_leaf=1,
                    name=item["name"],
                    depth=BOOK_SYSTEM_NODE_DEPTH[BOOK_SYSTEM_ROLES_ID] + 1,
                    data=item.get("data"),
                    content=item.get("content"),
                    type=BookNodeCategory.ROLES.code,
                )
                for item in items
            ]
            self.db.add_all(nodes)
            await self.db.flush()

            # 所有角色一次提交，任意一条失败时由下面的 rollback 整批回滚。
            await self.db.commit()
            return nodes
        except Exception:
            await self.db.rollback()
            raise

    async def batch_edit_roles(
            self,
            uid: int,
            items: list[dict],
    ) -> list[BookNode]:
        """在一次事务中批量编辑当前用户的角色节点。"""
        if not items:
            raise ServiceWarning("角色列表不能为空")

        role_ids = [item["id"] for item in items]
        if len(role_ids) != len(set(role_ids)):
            raise ServiceWarning("角色列表中存在重复的 id")

        try:
            node_map = {
                node.id: node
                for node in await self.book_dao.get_nodes_by_ids(
                    node_ids=role_ids,
                    uid=uid,
                )
            }
            nodes: list[BookNode] = []
            for item in items:
                node = node_map.get(item["id"])
                if not node or node.bid != item["bid"]:
                    raise ServiceWarning(f"角色不存在或无权编辑: {item['id']}")
                if node.type != BookNodeCategory.ROLES.code:
                    raise ServiceWarning(f"节点不是角色类型: {item['id']}")

                if item.get("name") is not None:
                    node.name = item["name"]
                if item.get("data") is not None:
                    node.data = item["data"]
                node.updateTime = datetime.now()
                self.db.add(node)
                nodes.append(node)

            # 编辑也采用整批原子提交，避免角色信息只更新一部分。
            await self.db.commit()
            return nodes
        except Exception:
            await self.db.rollback()
            raise

    async def delete_node_(
            self,
            bid: str,
            node_id: int,
            uid: int
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

        bound_chapter = await self.book_dao.get_chapter_by_detail_outline_ids(
            bid=bid,
            uid=uid,
            detail_outline_ids=to_delete_ids,
        )
        if bound_chapter:
            raise ServiceWarning("该细纲已关联章节，请先解绑后再删除")

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
        # if book.status != 3:
        #    raise ServiceWarning("请先下架书籍后再删除")

        # 3️ 删除节点
        await self.book_dao.delete_nodes_by_bid(bid, uid)

        # 4 删除书籍
        await self.book_dao.hard_delete_book(bid, uid)

        return {
            "bid": bid,
            "deleted": True
        }

    async def auto_create_book(self, user_id: int, title: str, summary: str,
                               roles: List[Character],
                               outline: str | None = None,
                               writing_style: str | None = None,
                               world_view: str | None = None,
                               chapters: List[ChapterData] | None = None) -> Book:

        # 1. 创建书籍根节点
        book = await self.create_book_with_tree(
            title=title, description=summary, uid=user_id, template_id="TPLXIAOSHUO"
        )
        if not book:
            return None

        for role in roles or []:
            await self.book_dao.add_child_node(
                bid=book.bid,
                uid=user_id,
                parent_node=None,
                parent_id=BOOK_SYSTEM_ROLES_ID,
                is_leaf=1,
                name=role.name,
                content=role.role,
                category=BookNodeCategory.ROLES,
                depth=BOOK_SYSTEM_NODE_DEPTH[BOOK_SYSTEM_ROLES_ID] + 1,
            )

        for chapter in chapters or []:
            await self.book_dao.add_child_node(
                bid=book.bid,
                uid=user_id,
                parent_node=None,
                parent_id=BOOK_SYSTEM_CONTENT_ID,
                is_leaf=1,
                name=chapter.title,
                content=chapter.content,
                category=BookNodeCategory.CONTENT,
                order=chapter.index,
                depth=BOOK_SYSTEM_NODE_DEPTH[BOOK_SYSTEM_CONTENT_ID] + 1,
            )

        # 世界观和大纲是可继续新增内容的虚拟目录，自动生成结果应作为真实子节点保存。
        container_fields = {
            BOOK_SYSTEM_WORLDVIEW_ID: (BookNodeCategory.WORLDVIEW, world_view),
            BOOK_SYSTEM_OUTLINE_ID: (BookNodeCategory.OUTLINE, outline),
        }

        for parent_id, (node_type, content) in container_fields.items():
            if content:
                await self.book_dao.add_child_node(
                    bid=book.bid,
                    uid=user_id,
                    parent_node=None,
                    parent_id=parent_id,
                    is_leaf=1,
                    name=node_type.key,
                    content=content,
                    category=node_type,
                    depth=BOOK_SYSTEM_NODE_DEPTH[parent_id] + 1,
                )

        if writing_style:
            # 写作要求是虚拟叶子节点，数据库记录只负责承载其内容。
            await self.book_dao.add_child_node(
                bid=book.bid,
                uid=user_id,
                parent_node=None,
                parent_id=BOOK_SYSTEM_NODE_PARENT[BOOK_SYSTEM_WRITING_STYLE_ID],
                is_leaf=BOOK_SYSTEM_NODE_IS_LEAF[BOOK_SYSTEM_WRITING_STYLE_ID],
                name=BOOK_SYSTEM_NODE_NAME[BOOK_SYSTEM_WRITING_STYLE_ID],
                data={"system_key": BOOK_SYSTEM_WRITING_STYLE_ID},
                content=writing_style,
                category=BookNodeCategory.WRITING_STYLE,
                depth=BOOK_SYSTEM_NODE_DEPTH[BOOK_SYSTEM_WRITING_STYLE_ID],
            )

        return book

    async def create_book_with_chapters(
            self,
            user_id: int,
            book_name: str,
            chapters: List[Chapter],
    ) -> Book | None:
        book = await self.create_book_with_tree(uid=user_id, title=book_name, description="",
                                                template_id=DEFAULT_TEMPLATE_ID)
        if book is None:
            raise ServerError(msg=f"创建书籍[{book_name}]失败")

        try:
            await self.book_dao.batch_add_child_nodes(
                user_id=user_id,
                bid=book.bid,
                parent_node=None,
                parent_id=BOOK_SYSTEM_CONTENT_ID,
                node_type=BookNodeCategory.CONTENT.code,
                depth=BOOK_SYSTEM_NODE_DEPTH[BOOK_SYSTEM_CONTENT_ID] + 1,
                chapter_data=chapters,
                is_leaf=1
            )
        except Exception as e:
            logger.error(f"鎵归噺鍐欏叆绔犺妭澶辫触: {e}")
            raise ServerError(msg="绔犺妭鍚屾鍏ュ簱澶辫触")

        return book

    async def export(self, user_id: int, bid: str) -> str:
        book = await self.book_dao.get_book_by_bid(bid, user_id)
        if book is None:
            raise NotFoundError(msg="小说不存在")

        book_name = book.title
        nodes = await self.book_dao.get_book_nodes(user_id=user_id, bid=bid)

        # 2. 使用 StringIO 作为高效的字符缓冲区（比 += 拼接快得多）
        output = io.StringIO()
        output.write(f"{book_name}\n")

        children_by_parent = {}
        for node in nodes:
            children_by_parent.setdefault(node.parent_id, []).append(node)

        legacy_content_root_ids = [
            node.id
            for node in nodes
            if node.parent_id in (None, 0) and node.type == BookNodeCategory.CONTENT.code and not node.content
        ]
        # 导出时同时兼容两类数据：新数据挂在虚拟正文 -6 下，旧数据挂在入库的正文根节点下。
        content_parent_ids = [BOOK_SYSTEM_CONTENT_ID, *legacy_content_root_ids]

        visited_node_ids = set()

        def write_children(parent_id: int) -> None:
            for child in children_by_parent.get(parent_id, []):
                if child.id in visited_node_ids:
                    continue
                visited_node_ids.add(child.id)

                output.write(f"{child.name}\n\n")
                if child.content:
                    output.write(child.content)
                    output.write("\n\n")

                write_children(child.id)

        for parent_id in content_parent_ids:
            write_children(parent_id)

        return quick_html_to_text(output.getvalue())

    @staticmethod
    async def download_novel_content(url: str, timeout: float = 120.0) -> str:
        """
        [Service] 异步下载小说内容
        :param url: 文件下载链接
        :param timeout: 超时时间
        :return: 文件的原始二进制内容 (bytes)
        """
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                logger.info(f"发起文件下载请求: {url}")
                response = await client.get(url)

                # 1. 校验状态码
                if response.status_code == 404:
                    raise NotFoundError(msg="下载链接已失效或文件不存在")
                if response.status_code != 200:
                    logger.error(f"下载失败，HTTP状态码: {response.status_code}")
                    raise RequestError(msg=f"远程服务器返回异常: {response.status_code}")

                # 2. 校验内容
                content = response.content
                if not content:
                    raise RequestError(msg="下载完成，但文件内容为空")

                # 3. 校验大小（建议选配：防止恶意下载超大文件导致内存崩溃）
                # 50MB 限制
                if len(content) > 10 * 1024 * 1024:
                    raise RequestError(msg="文件过大，超出系统处理范围")

                # 使用多编码尝试解码
                decoded_text = None
                for encoding in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
                    try:
                        decoded_text = content.decode(encoding)
                        return decoded_text
                    except UnicodeDecodeError:
                        continue

                if decoded_text is None:
                    decoded_text = content.decode("utf-8", errors="ignore")
                    logger.warning("所有编码解码失败，强制使用 utf-8 ignore 模式")
                    return decoded_text

                return None

        except httpx.ConnectTimeout:
            logger.error(f"连接服务器超时: {url}")
            raise ServerError(msg="连接服务器超时，请稍后重试")
        except httpx.RequestError as e:
            logger.error(f"网络异常 (httpx.RequestError): {str(e)}")
            raise ServerError(msg="网络请求异常，请检查链接或稍后重试")
        except Exception as e:
            logger.error(f"下载函数内部未知错误: {str(e)}")
            raise ServerError(msg="文件下载服务暂不可用")

    @staticmethod
    async def get_deconstruct_generate_list(
            db: AsyncSession,
            user_id: int,
            page: int,
            pageSize: int
    ):
        rows, total = await BookDAO.get_deconstruct_list_dao(
            db=db,
            user_id=user_id,
            page=page,
            pageSize=pageSize
        )

        list_data = [
            BookDeconstructItemVO(
                requestId=row.requestId,
                title=row.title,
                status=row.status,
                createdAt=row.createdAt
            )
            for row in rows
        ]

        return PageResp(
            list=list_data,
            total=total,
            page=page,
            pageSize=pageSize
        )


    @staticmethod
    async def get_by_request_id(db: AsyncSession, request_id: str, userId:int) -> BookDeconstructRecord | None:
        stmt = select(BookDeconstructRecord).where(
            BookDeconstructRecord.requestId == request_id,
            BookDeconstructRecord.userId == userId
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def logical_delete(db: AsyncSession, record: BookDeconstructRecord):
        record.isDelete = 1
        db.add(record)
        await db.commit()
        return True

    @staticmethod
    async def delete_by_request_id(db: AsyncSession, request_id: str, userId:int):
        record = await BookService.get_by_request_id(db, request_id, userId)
        if not record:
            raise ServerError(msg="拆书记录不存在")
        await BookService.logical_delete(db, record)
        return True
