import json
from typing import Optional
from fastapi import APIRouter, Depends, Query
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from common.config.get_db import get_db
from common.response.response_util import ResponseUtil
from core.deps.auth import get_login_user
from core.entity.vo.book_node_schema import BookResp, CreateBookReq, BookNodeDetailResp, UpdateBookNodeReq, \
    EditBookNodeReq, EditBookNodeResp, AddChapterResp, AddBookNodeReq, DeleteBookNodeReq, OfflineBookReq, EditBookReq, \
    HardDeleteBookReq
from service.book_service import BookService

bookController = APIRouter()


@bookController.get("/book/tree", name="作品树状结构")
async def get_book_nodes(bid: str,
                         max_depth: Optional[int] = Query(None, description="最大深度限制"), # 增加可选参数
                         db: AsyncSession = Depends(get_db),
                         user=Depends(get_login_user)):
    book_service = BookService(db)
    tree = await book_service.get_tree(bid, uid=user.pkId, max_depth=max_depth)
    return ResponseUtil.success(data=tree)

@bookController.get("/book/node/children", name="作品树状结构")
async def get_book_children_nodes(bid: str,
                         root_id:int,
                         db: AsyncSession = Depends(get_db),
                         user=Depends(get_login_user)):
    book_service = BookService(db)
    tree = await book_service.get_sub_tree(bid, uid=user.pkId, root_id=root_id)
    return ResponseUtil.success(data=tree)

@bookController.post("/user/chapter/add", name="新增树状结构章节/节点")
async def add_chapter(
    req: AddBookNodeReq,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_login_user)
):
    """
    新增章节接口
    """
    if req.data:
        data = json.loads(req.data)
    else:
        data = None

    content = req.content if req.content else None

    chapter = await BookService.add_chapter(
        db,
        uid=user.pkId,
        bid=req.bid,
        parent_id=req.parent_id,
        is_leaf=req.is_leaf,
        name=req.name,
        data=data,
        content=content
    )

    resp = AddChapterResp(
        id=chapter.id,
        bid=chapter.bid,
        parent_id=chapter.parent_id,
        is_leaf=chapter.is_leaf,
        name=chapter.name,
        data=chapter.data,
        content=content

    )

    logger.info("新增节点成功 响应体：{}".format(resp))

    return ResponseUtil.success(data=resp)


@bookController.post("/delete", name="删除书籍节点")
async def delete_book_node(
    req: DeleteBookNodeReq,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_login_user)

):
    """
    删除节点（包含子树）
    """
    result = await BookService.delete_node_(
        db,
        bid=req.bid,
        node_id=req.id,
        uid=user.pkId
    )

    return ResponseUtil.success(data=result)


@bookController.post("/user/chapter/edit", name="编辑树状结构章节/节点")
async def edit_book_node(
    req: EditBookNodeReq,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_login_user)
):
    """
    编辑章节 / 节点接口
    """
    if req.data:
        data = json.loads(req.data)
    else:
        data = None

    node = await BookService.edit_book_node(
        db,
        node_id=req.id,
        uid=user.pkId,
        bid=req.bid,
        name=req.name,
        data=data
    )

    # 显式走 Pydantic v2（方案一）
    resp_data = EditBookNodeResp.model_validate(node)

    return ResponseUtil.success(data=resp_data)


@bookController.get("/book/detail", name="书籍详情节点概要内容")
async def get_book_node_detail(
    id: int = Query(..., description="mc_book_node 节点ID"),
    bid: str = Query(..., description="mc_book_node bidID"),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_login_user)
):
    """
    获取书籍节点详情接口
    """
    node = await BookService.get_book_node_detail(
        db,
        node_id=id,
        uid=user.pkId,
        bid=bid
    )

    #  关键点：显式走 Pydantic v2 序列化（方案一）
    resp_data = BookNodeDetailResp.model_validate(node)

    return ResponseUtil.success(data=resp_data)


@bookController.post("/user/book/edit", name="编辑书籍节点概要内容")
async def edit_book_node(
    req: UpdateBookNodeReq,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_login_user)

):
    """
    编辑书籍节点内容接口
    """
    node = await BookService.update_book_node_content(
        db,
        node_id=req.id,
        uid=user.pkId,
        bid=req.bid,
        content=req.content,
        data=req.data,
    )

    #  显式走 Pydantic v2（方案一）
    resp_data = BookNodeDetailResp.model_validate(node)

    return ResponseUtil.success(data=resp_data)


@bookController.get("/book/list", name="书籍列表")
async def list_books(
    status: Optional[int] = Query(0, description="书籍状态"),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_login_user)
):
    """
    获取书籍列表接口
    """
    data = await BookService.list_books(
        db,
        status=status,
        uid=user.pkId
    )

    # 关键：手动走 Pydantic v2 序列化
    resp_data = [BookResp.model_validate(item) for item in data]
    return ResponseUtil.success(data=resp_data)


@bookController.post("/book/create", response_model=BookResp, name="创建书籍")
async def create_book(
    req: CreateBookReq,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_login_user)

):
    """
    创建书籍（自动初始化树结构）
    """
    service = BookService(db)

    book = await service.create_book_with_tree(
        db,
        title=req.title,
        description=req.description,
        uid=user.pkId,
        template_id=req.template_id,
    )

    # 显式序列化（你现在已经统一这么做）
    resp = BookResp.model_validate(book)

    return ResponseUtil.success(data=resp)


@bookController.post("/book/edit", name="编辑书籍信息")
async def edit_book(
    req: EditBookReq,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_login_user)

):
    """
    编辑书籍信息接口
    """
    service = BookService(db)

    book = await service.edit_book(
        db,
        template_id=req.template_id,
        bid=req.bid,
        uid=user.pkId,
        title=req.title,
        bookType=req.bookType,
        description=req.description,
    )

    # 显式走 Pydantic v2（现在的标准做法）
    resp = BookResp.model_validate(book)

    return ResponseUtil.success(data=resp)


@bookController.post("/book/offline", name="下架书籍")
async def offline_book(
    req: OfflineBookReq,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_login_user)
):
    """
    下架书籍（逻辑删除）
    """
    service = BookService(db)
    result = await service.offline_book(db, bid=req.bid, uid=user.pkId)

    return ResponseUtil.success(data=result)


@bookController.post("/hardDelete", name="彻底删除书籍")
async def hard_delete_book(
    req: HardDeleteBookReq,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_login_user)

):
    """
    真正删除书籍接口
    """
    service = BookService(db)
    result = await service.hard_delete_book(db, bid=req.bid, uid=user.pkId)

    return ResponseUtil.success(data=result)