import json
import os
import textwrap
import uuid
from typing import Optional, List
from urllib.parse import urlparse

import httpx
from cachetools import TTLCache
from fastapi import APIRouter, Depends, Query, Body, BackgroundTasks
from loguru import logger
# from openai.resources.skills import content
from sqlalchemy.ext.asyncio import AsyncSession

from ai.adapters.enums import AIProvider, AIAction
from common.config.get_db import get_db, get_db_context
from common.exception.errors import RequestError, NotFoundError, ServerError
from common.response.response_util import ResponseUtil
from common.utils.text_util import generate_text_sha256_id, strip_html_tags
from core.deps.auth import get_current_user, check_user_quota_or_raise
from core.entity.do.book_deconstruct_record_do import BookDeconstructRecord
from core.entity.do.users_do import User
from core.entity.vo.book_node_schema import BookResp, CreateBookReq, BookNodeDetailResp, UpdateBookNodeReq, \
    EditBookNodeReq, EditBookNodeResp, AddChapterResp, AddBookNodeReq, DeleteBookNodeReq, OfflineBookReq, EditBookReq, \
    HardDeleteBookReq, BookSearchResp, BatchAddRoleItemReq, BatchEditRoleItemReq, BindChapterDetailOutlineReq, \
    BindChapterDetailOutlineResp, ChapterDetailOutlineStatusResp
from core.entity.vo.bool_vo import AutoCreateBookReq
from core.entity.vo.confirm_import_req import ConfirmImportRequest
from core.processor.book_processor import Chapter, NovelProcessor
from service.ai_prompt_service import PromptService
from service.ai_service import AIService
from service.book_service import (
    BookService,
    DETAIL_OUTLINE_AI_LEVEL,
    DETAIL_OUTLINE_TEMPLATE_KEY,
)

bookController = APIRouter()


@bookController.get("/book/tree", name="作品树状结构")
async def get_book_nodes(bid: str,
                         max_depth: Optional[int] = Query(None, description="最大深度限制"),  # 增加可选参数
                         db: AsyncSession = Depends(get_db),
                         current_user=Depends(get_current_user)):
    book_service = BookService(db)
    tree = await book_service.get_tree(bid, uid=current_user.pkId, max_depth=max_depth)
    return ResponseUtil.success(data=tree)


@bookController.get("/book/node/children", name="作品树状结构")
async def get_book_children_nodes(bid: str,
                                  root_id: int,
                                  db: AsyncSession = Depends(get_db),
                                  current_user=Depends(get_current_user)):
    book_service = BookService(db)
    tree = await book_service.get_sub_tree(bid, uid=current_user.pkId, root_id=root_id)
    return ResponseUtil.success(data=tree)


@bookController.post("/user/chapter/add", name="新增树状结构章节/节点")
async def add_chapter(
        req: AddBookNodeReq,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """
    新增章节接口
    """
    if req.data:
        data = json.loads(req.data)
    else:
        data = None

    content = req.content if req.content else None

    book_service = BookService(db=db)
    chapter = await book_service.add_chapter(
        uid=current_user.pkId,
        bid=req.bid,
        parent_id=req.parent_id,
        is_leaf=req.is_leaf,
        name=req.name,
        data=data,
        content=content,
        type=req.type
    )

    resp = AddChapterResp(
        id=chapter.id,
        bid=chapter.bid,
        parent_id=chapter.parent_id,
        is_leaf=chapter.is_leaf,
        name=chapter.name,
        data=chapter.data,
        content=content,
        detail_outline_id=chapter.detail_outline_id,

    )

    logger.info("新增节点成功 响应体：{}".format(resp))

    return ResponseUtil.success(data=resp)


@bookController.post("/book/chapter/bindDetailOutline", name="章节关联细纲")
async def bind_chapter_detail_outline(
        req: BindChapterDetailOutlineReq,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user),
):
    """关联细纲后立即根据章节正文异步生成细纲；传 null 时仅解除关联。"""
    book_service = BookService(db)
    chapter = await book_service.bind_chapter_detail_outline(
        uid=current_user.pkId,
        bid=req.bid,
        chapter_id=req.chapterId,
        detail_outline_id=req.detailOutlineId,
    )

    if req.detailOutlineId is None:
        return ResponseUtil.success(data=BindChapterDetailOutlineResp(
            chapterId=chapter.id,
            detailOutlineId=None,
        ))

    chapter, detail_outline = await book_service.get_chapter_detail_outline_for_generation(
        uid=current_user.pkId,
        bid=req.bid,
        chapter_id=chapter.id,
    )
    user_id = current_user.pkId
    bid = req.bid
    detail_outline_id = detail_outline.id

    async def save_result(ai_rsp):
        async with get_db_context() as task_db:
            await BookService(task_db).save_generated_detail_outline(
                uid=user_id,
                bid=bid,
                detail_outline_id=detail_outline_id,
                content=ai_rsp.content,
            )

    request_id = await AIService(db).execute(
        db=db,
        user=current_user,
        action_type=AIAction.Execute,
        level=DETAIL_OUTLINE_AI_LEVEL,
        bid=bid,
        template_key=DETAIL_OUTLINE_TEMPLATE_KEY,
        inputs={"novel": strip_html_tags(chapter.content or "")},
        background_tasks=background_tasks,
        on_success_callback=save_result,
    )
    return ResponseUtil.success(data=BindChapterDetailOutlineResp(
        chapterId=chapter.id,
        detailOutlineId=detail_outline_id,
        requestId=request_id,
    ))


@bookController.get("/book/chapter/detailOutline/status", name="查询章节细纲关联状态")
async def get_chapter_detail_outline_status(
        bid: str,
        chapterId: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user),
):
    """仅查询章节是否关联有效细纲，不修改关联关系。"""
    chapter, detail_outline = await BookService(db).get_chapter_detail_outline_status(
        uid=current_user.pkId,
        bid=bid,
        chapter_id=chapterId,
    )
    return ResponseUtil.success(data=ChapterDetailOutlineStatusResp(
        chapterId=chapter.id,
        isBound=detail_outline is not None,
        detailOutlineId=detail_outline.id if detail_outline else None,
        detailOutlineName=detail_outline.name if detail_outline else None,
    ))


@bookController.post("/user/role/batch/add", name="批量新增角色")
async def batch_add_roles(
        reqs: List[BatchAddRoleItemReq] = Body(..., min_length=1, max_length=100),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user),
):
    """批量新增角色；请求体直接提交角色数组。"""
    book_service = BookService(db=db)
    nodes = await book_service.batch_add_roles(
        uid=current_user.pkId,
        items=[req.model_dump() for req in reqs],
    )

    resp = [
        AddChapterResp(
            id=node.id,
            bid=node.bid,
            parent_id=node.parent_id,
            is_leaf=node.is_leaf,
            name=node.name,
            data=node.data,
            content=node.content,
        )
        for node in nodes
    ]
    return ResponseUtil.success(data=resp)


@bookController.post("/delete", name="删除书籍节点")
async def delete_book_node(
        req: DeleteBookNodeReq,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)

):
    """
    删除节点（包含子树）
    """
    book_service = BookService(db)
    result = await book_service.delete_node_(
        bid=req.bid,
        node_id=req.id,
        uid=current_user.pkId
    )

    return ResponseUtil.success(data=result)


@bookController.post("/user/chapter/edit", name="编辑树状结构章节/节点")
async def edit_book_node(
        req: EditBookNodeReq,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """
    编辑章节 / 节点接口
    """
    books = BookService(db)

    if req.data:
        data = json.loads(req.data)
    else:
        data = None

    node = await books.edit_book_node(
        node_id=req.id,
        uid=current_user.pkId,
        bid=req.bid,
        name=req.name,
        data=data
    )

    # 显式走 Pydantic v2（方案一）
    resp_data = EditBookNodeResp.model_validate(node)

    return ResponseUtil.success(data=resp_data)


@bookController.post("/user/role/batch/edit", name="批量编辑角色")
async def batch_edit_roles(
        reqs: List[BatchEditRoleItemReq] = Body(..., min_length=1, max_length=1000),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user),
):
    """批量编辑角色；请求体直接提交角色数组。"""
    book_service = BookService(db=db)
    nodes = await book_service.batch_edit_roles(
        uid=current_user.pkId,
        items=[req.model_dump() for req in reqs],
    )
    resp = [EditBookNodeResp.model_validate(node) for node in nodes]
    return ResponseUtil.success(data=resp)


@bookController.get("/book/detail", name="书籍详情节点概要内容")
async def get_book_node_detail(
        id: int = Query(..., description="mc_book_node 节点ID"),
        bid: str = Query(..., description="mc_book_node bidID"),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """
    获取书籍节点详情接口
    """
    books = BookService(db)

    node = await books.get_book_node_detail(
        node_id=id,
        uid=current_user.pkId,
        bid=bid
    )

    #  关键点：显式走 Pydantic v2 序列化（方案一）
    resp_data = BookNodeDetailResp.model_validate(node)

    return ResponseUtil.success(data=resp_data)


@bookController.post("/user/book/edit", name="编辑书籍节点概要内容")
async def edit_book_node(
        req: UpdateBookNodeReq,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    编辑书籍节点内容接口
    """
    books = BookService(db)

    node = await books.update_book_node_content(
        node_id=req.id,
        uid=current_user.pkId,
        bid=req.bid,
        book_len=req.len,
        content=req.content,
        data=req.data
    )

    #  显式走 Pydantic v2（方案一）
    resp_data = BookNodeDetailResp.model_validate(node)

    return ResponseUtil.success(data=resp_data)


@bookController.get("/book/list", name="书籍列表")
async def list_books(
        status: Optional[int] = Query(0, description="书籍状态"),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """
    获取书籍列表接口
    """

    books = BookService(db)

    data = await books.list_books(
        status=status,
        uid=current_user.pkId
    )

    # 关键：手动走 Pydantic v2 序列化
    resp_data = [BookResp.model_validate(item) for item in data]
    return ResponseUtil.success(data=resp_data)


@bookController.get("/book/search", name="book content search")
async def search_book_content(
        bid: str = Query(..., description="book bid"),
        keyword: str = Query(..., description="keyword"),
        limit: Optional[int] = Query(None, ge=1, le=500, description="max matched chapter nodes"),
        snippetSize: int = Query(24, ge=5, le=100, description="snippet size around keyword"),
        maxSnippetsPerNode: Optional[int] = Query(None, ge=1, le=200, description="max snippets per chapter node"),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    books = BookService(db)
    data: BookSearchResp = await books.search_book_content(
        uid=current_user.pkId,
        bid=bid,
        keyword=keyword,
        limit=limit,
        snippet_size=snippetSize,
        max_snippets_per_node=maxSnippetsPerNode,
    )
    return ResponseUtil.success(data=data)


@bookController.post("/book/create", response_model=BookResp, name="创建书籍")
async def create_book(
        req: CreateBookReq,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """
    创建书籍（自动初始化树结构）
    """
    service = BookService(db)
    book = await service.create_book_with_tree(
        title=req.title,
        description=req.description,
        uid=current_user.pkId,
        template_id=req.template_id,
        coverUrl=req.coverUrl,
    )

    # 显式序列化（你现在已经统一这么做）
    resp = BookResp.model_validate(book)

    return ResponseUtil.success(data=resp)


@bookController.post("/book/autoCreate", response_model=BookResp, name="自动创建书籍")
async def create_book_auto(
        req: AutoCreateBookReq,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    service = BookService(db)
    book = await service.auto_create_book(user_id=current_user.pkId,
                                          title=req.title,
                                          summary=req.summary,
                                          roles=req.characters,
                                          outline=req.fullOutlineText,
                                          writing_style=req.writingStyle,
                                          world_view=req.worldView,
                                          chapters=req.chapters, )
    if not book:
        return ResponseUtil.error(msg="未知错误")
    else:
        resp = BookResp.model_validate(book)
        return ResponseUtil.success(data=resp)


@bookController.post("/book/edit", name="编辑书籍信息")
async def edit_book(
        req: EditBookReq,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """
    编辑书籍信息接口
    """
    service = BookService(db)

    book = await service.edit_book(
        template_id=req.template_id,
        bid=req.bid,
        uid=current_user.pkId,
        title=req.title,
        bookType=req.bookType,
        description=req.description,
        coverUrl=req.coverUrl,
    )

    # 显式走 Pydantic v2（现在的标准做法）
    resp = BookResp.model_validate(book)

    return ResponseUtil.success(data=resp)


@bookController.post("/book/offline", name="下架书籍")
async def offline_book(
        req: OfflineBookReq,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """
    下架书籍（逻辑删除）
    """
    service = BookService(db)
    result = await service.offline_book(bid=req.bid, uid=current_user.pkId)

    return ResponseUtil.success(data=result)


@bookController.post("/hardDelete", name="彻底删除书籍")
async def hard_delete_book(
        req: HardDeleteBookReq,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """
    真正删除书籍接口
    """
    service = BookService(db)
    result = await service.hard_delete_book(bid=req.bid, uid=current_user.pkId)

    return ResponseUtil.success(data=result)


parse_cache = TTLCache(maxsize=1000, ttl=1800)


@bookController.post(path="/book/import", name="导入书籍获取章节信息")
async def import_book(url: str = Body(..., embed=True, description="txt连接")):
    """
    通过 URL 导入小说：校验 -> 下载 -> 自动拆分
    """
    # 1. 识别后缀名
    # 去除 URL 可能带有的参数（如 ?token=xxx）后再检查
    clean_url = url.split('?')[0].lower()
    if not clean_url.endswith('.txt'):
        logger.warning(f"拒绝非TXT资源下载: {url}")
        raise RequestError(msg="仅支持 .txt 格式的文件下载")

    # 2. 异步下载文件内容
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            logger.info(f"开始下载小说资源: {url}")
            response = await client.get(url)

            # 检查响应状态
            if response.status_code != 200:
                logger.error(f"下载失败，状态码: {response.status_code}")
                raise NotFoundError(
                    msg="无法下载指定资源，请检查链接有效性"
                )

            # 获取原始内容（二进制流）
            raw_content = response.content
            if not raw_content:
                raise RequestError(msg="下载的文件内容为空")

    except httpx.RequestError as e:
        logger.error(f"网络请求异常: {str(e)}")
        raise ServerError(msg="网络请求异常，请稍后重试")

    # 3. 编码解码与章节切分
    try:
        # 使用多编码尝试解码
        decoded_text = None
        for encoding in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
            try:
                decoded_text = raw_content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        if decoded_text is None:
            decoded_text = raw_content.decode("utf-8", errors="ignore")
            logger.warning("所有编码解码失败，强制使用 utf-8 ignore 模式")

        processor = NovelProcessor()
        # 调用我们之前的 NovelProcessor 进行切分
        chapters: List[Chapter] = processor.split_text(decoded_text)

        if not chapters:
            return ResponseUtil.error(msg="未能在文件中识别到任何有效章节")

        logger.info(f"成功通过链接导入小说，共计 {len(chapters)} 章")

        task_id = uuid.uuid4().hex.lower().replace("-", "")
        parse_cache[task_id] = chapters

        data = [
            {
                "index": c.index,
                "title": c.title,
                "word_count": c.word_count  # 建议带上字数，增加产品质感
            }
            for c in chapters
        ]

        path = urlparse(clean_url).path
        filename = os.path.basename(path)

        return ResponseUtil.success(data={"taskId": task_id, "chapter": data, "fileName": filename})

    except Exception as e:
        logger.error(f"解析小说内容时发生致命错误: {str(e)}")
        raise ServerError(msg="小说解析失败")


@bookController.post(path="/book/confirm", name="导入作品后确认创建书籍")
async def confirm(
        req: ConfirmImportRequest,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    # 1. 从缓存中获取预解析的完整数据
    # 注意：parse_cache 应该在模块级别定义
    cached_chapters = parse_cache.get(req.taskId)

    if not cached_chapters:
        logger.warning(f"任务已过期或不存在: {req.taskId}")
        raise ServerError(
            msg="解析任务已过期，请重新上传文件"
        )

    # 2. 根据用户选中的索引过滤章节
    # cached_chapters 里面是 List[Chapter] 对象
    selected_chapters = [
        c for c in cached_chapters
        if c.index in req.selectedIndices
    ]

    if not selected_chapters:
        raise ServerError(msg="未能匹配到选中的章节，请刷新页面重试")

    try:
        book_service = BookService(db)
        book = await book_service.create_book_with_chapters(user_id=current_user.pkId, book_name=req.bookName,
                                                            chapters=selected_chapters)
        parse_cache.pop(req.taskId, None)
        return ResponseUtil.success(data=book)

    except Exception as e:
        logger.error(f"确认导入失败: {str(e)}")
        raise ServerError(msg="保存书籍失败，请联系管理员")


@bookController.post(path="/book/deconstruct", name="拆书")
async def deconstruct(
        background_tasks: BackgroundTasks,
        url: str = Body(..., embed=True, description="txt连接"),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    content = await BookService.download_novel_content(url=url)

    title = await BookService.extract_book_title(url=url)

    if not content:
        raise NotFoundError(msg="资源不存在")

    book_sha256_id = generate_text_sha256_id(text=content)

    tool_key = "wenyuan_deconstructor_2"
    params = {
        "noval": content
    }
    prompt_service = PromptService(db)
    user_prompt = await prompt_service.render_prompt_tool(book=None, templateKey=tool_key, inputs=params)

    level = AIProvider.DOUBAO.value
    frozen_token_size = len(user_prompt) * 2
    logger.info(f"[拆书] {textwrap.shorten(user_prompt, width=64, placeholder="...")} 预冻结:{frozen_token_size}")
    await check_user_quota_or_raise(frozen_token_length=frozen_token_size, user_info=current_user, level=level)

    ai_service = AIService(db)
    request_id, _ = await ai_service.prepare_and_record_request(
        user=current_user,
        bid=book_sha256_id,
        origin_prompt="拆书",
        user_prompt=user_prompt,
        level=level,
        action_type=AIAction.Deconstruct,
        background_tasks=background_tasks
    )

    # 6. 创建拆书记录
    deconstruct_record = BookDeconstructRecord(
        userId=current_user.pkId,
        requestId=request_id,
        bookHash=book_sha256_id,
        title=title,
        sourceUrl=url,
    )

    db.add(deconstruct_record)

    await db.commit()

    logger.info(
        f"[拆书记录创建成功] "
        f"user:{current_user.pkId} "
        f"requestId:{request_id}"
    )

    print("request_id:{}".format(request_id))
    return ResponseUtil.success(data=request_id)


@bookController.post(path="/book/export", name="导出作品")
async def export(
        bid: str = Body(..., embed=True),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    book_service = BookService(db)
    text = await book_service.export(bid=bid, user_id=current_user.pkId)
    # write_simple_txt(uuid.uuid4().hex + ".txt", text)
    # todo 导出文本上传到外网-->发地址
    return ResponseUtil.success(data=text)


@bookController.get("/book/deconstruct/list", summary="拆书生成记录列表")
async def get_deconstruct_generate_list(
    page: int = Query(1, ge=1, description="页码"),
    pageSize: int = Query(20, ge=1, le=999, description="每页数量"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)

):
    data = await BookService.get_deconstruct_generate_list(
        db=db,
        user_id=current_user.pkId,
        page=page,
        pageSize=pageSize
    )

    return ResponseUtil.success(data=data)


@bookController.post("/book/deconstruct/delete", summary="逻辑删除拆书历史记录")
async def delete_deconstruct_record(
        requestId: str = Body(..., embed=True, description="拆书任务requestId"),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)

):
    await BookService.delete_by_request_id(db, requestId, userId=current_user.pkId)

    return ResponseUtil.success(msg="删除成功")
