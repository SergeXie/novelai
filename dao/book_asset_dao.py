from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Tuple

from core.entity.do.books import McBookAsset


class BookAssetDao:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_book_assets_by_page(
            self,
            user_id: int,
            page: int = 1,
            page_size: int = 10
    ) -> Tuple[List[McBookAsset], int]:
        """
        分页查询用户的拆书历史
        :param user_id: 用户ID
        :param page: 当前页码 (从1开始)
        :param page_size: 每页条数
        :return: (资产列表, 总条数)
        """
        # 1. 计算偏移量
        offset = (page - 1) * page_size

        # 2. 构建基础查询语句 (过滤已删除的数据)
        base_stmt = select(McBookAsset).where(
            McBookAsset.user_id == user_id,
            McBookAsset.is_delete == 0
        )

        # 3. 查询总数 (用于前端分页器计算总页数)
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_count = await self.db.scalar(count_stmt) or 0

        # 4. 执行分页查询 (按创建时间倒序)
        query_stmt = base_stmt.order_by(
            McBookAsset.created_at.desc()
        ).offset(offset).limit(page_size)

        result = await self.db.execute(query_stmt)
        assets = result.scalars().all()

        return list(assets), total_count