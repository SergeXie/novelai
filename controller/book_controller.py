from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from common.config.get_db import get_db
from common.response.response_util import ResponseUtil
from service.book_service import BookService

bookController = APIRouter()

@bookController.get("/book/tree")
async def get_book_nodes(bid: str, db: AsyncSession = Depends(get_db)):
    book_service = BookService(db)
    tree = await book_service.get_tree(bid)
    return ResponseUtil.success(data=tree)