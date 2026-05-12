from typing import List, Dict, Any
from pydantic import TypeAdapter

from core.entity.vo.base_vo import PageResp
from core.entity.vo.bool_vo import BookAssetVO
from dao.book_asset_dao import BookAssetDao


class BookService:
    def __init__(self, book_dao: BookAssetDao):
        self.book_dao = book_dao

    async def get_user_destruct_history(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 10
    ) -> PageResp[BookAssetVO]:  # 指定返回类型为泛型分页模型
        """
        获取用户拆书历史记录（分页并返回通用分页模型）
        """
        # 1. 调用 DAO 获取 DO 列表和总数
        assets_do, total_count = await self.book_dao.get_book_assets_by_page(
            user_id=user_id,
            page=page,
            page_size=page_size
        )

        # 2. 批量将 DO 转换为 VO
        vo_adapter = TypeAdapter(List[BookAssetVO])
        assets_vo = vo_adapter.validate_python(assets_do)

        # 3. 返回通用的分页模型实例
        # 注意：这里将字段名从 items 改为了你 PageResp 定义中的 list
        return PageResp[BookAssetVO](
            list=assets_vo,
            total=total_count,
            page=page,
            pageSize=page_size
        )