import io
import os
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
from core.entity.vo.book_node_schema import NodeTreeSchema
from core.entity.vo.bool_vo import Character, ChapterData
from core.entity.vo.generate_log_vo import BookDeconstructItemVO
from core.enums.node_type import BookNodeCategory
from core.processor.book_processor import Chapter
from dao.book_dao import BookDAO
from dao.template_dao import TemplateDAO

DEFAULT_TEMPLATE_ID = "TPLXIAOSHUO"


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

    async def count_book_words(self, bid: str) -> int:
        """
        统计书籍字数（去HTML）
        """
        contents = await self.book_dao.get_contents_by_bid(bid)
        total = 0
        for content in contents:
            clean_text = strip_html_tags(content)
            total += len(clean_text)
        return total

    async def get_tree(self, bid: str, uid: int, max_depth: Optional[int] = None) -> List[NodeTreeSchema]:
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

    async def _create_nodes_from_template(self,
                                          uid: int,
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
            book_len: int | None,
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
            category=BookNodeCategory.CONTENT
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

        # 2. 获取一级分类节点
        nodes = await self.book_dao.get_book_nodes(bid=book.bid, user_id=user_id, max_depth=1)

        # 3. 定义简单字段的映射配置 (类型 -> 对应的内容)
        # 这样可以处理 outline, writing_style, world_view 这种单点内容
        simple_fields = {
            BookNodeCategory.WORLDVIEW: world_view,
            BookNodeCategory.OUTLINE: outline

        }

        notify_fields = {
            BookNodeCategory.WRITING_STYLE: writing_style,
        }

        for node in nodes:
            node_type = BookNodeCategory.from_code(code=node.type)

            # A. 处理角色列表 (多条)
            if node_type == BookNodeCategory.ROLES and roles:
                for role in roles:
                    await self.book_dao.add_child_node(
                        bid=book.bid, uid=user_id, parent_node=node, is_leaf=1,
                        name=role.name, content=role.role
                    )

            # B. 处理章节列表 (多条 + 排序)
            elif node_type == BookNodeCategory.CONTENT and chapters:
                for chapter in chapters:
                    await self.book_dao.add_child_node(bid=book.bid, uid=user_id, parent_node=node, is_leaf=1,
                                                       name=chapter.title, content=chapter.content,
                                                       order=chapter.index)

            # C. 处理其他简单文本节点 (单条)
            elif node_type in simple_fields and (content := simple_fields[node_type]):
                await self.book_dao.add_child_node(
                    bid=book.bid, uid=user_id, parent_node=node, is_leaf=1,
                    name=node_type.key, content=content
                )
            elif node_type in notify_fields and (content := notify_fields[node_type]):
                await self.book_dao.update_node_content(node=node, book_len=len(content), content=content)

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

        content_root_nodes = await self.book_dao.get_nodes_by_parent_id(bid=book.bid, parent_id=0)
        # 使用 next() 配合生成器更优雅地查找
        parent_node = next(
            (node for node in content_root_nodes if node.type == BookNodeCategory.CONTENT.code),
            None
        )

        if not parent_node:
            raise ServerError(msg="未找到书籍内容根节点结构")

        try:
            await self.book_dao.batch_add_child_nodes(
                user_id=user_id,
                bid=book.bid,
                parent_node=parent_node,
                chapter_data=chapters,
                is_leaf=1
            )
        except Exception as e:
            logger.error(f"批量写入章节失败: {e}")
            # 这里建议根据业务需求考虑是否需要回滚已创建的书籍（如果是同一个事务的话）
            raise ServerError(msg="章节同步入库失败")

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

        # 3. 寻找内容根节点（使用 next 提高效率，避免全量循环）
        content_root = next(
            (node for node in nodes if node.type == BookNodeCategory.CONTENT.code),
            None
        )

        if not content_root:
            return ""

        # 4. 按父子关系递归导出，兼容“正文 -> 卷 -> 章节”等多级结构。
        children_by_parent = {}
        for node in nodes:
            children_by_parent.setdefault(node.parent_id, []).append(node)

        visited_node_ids = set()

        def write_children(parent_id: int) -> None:
            for child in children_by_parent.get(parent_id, []):
                # 防止异常脏数据形成循环关系，导致递归无法结束。
                if child.id in visited_node_ids:
                    continue
                visited_node_ids.add(child.id)

                output.write(f"{child.name}\n\n")
                if child.content:
                    output.write(child.content)
                    output.write("\n\n")

                write_children(child.id)

        write_children(content_root.id)

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
