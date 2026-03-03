from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from core.entity.do.generate_log import AiNovelGenerateLog
from .base import BaseDAO

class AILogDAO(BaseDAO[AiNovelGenerateLog]):
    def __init__(self, db: AsyncSession):
        super().__init__(AiNovelGenerateLog, db)

    async def get_usage_sum(self, user_id: int, start_time: datetime = None, end_time: datetime = None) -> tuple[int, int]:
        """
        核心查询下放：根据时间范围统计输入和输出字符数
        """
        # 构建基础查询
        stmt = select(
            func.coalesce(func.sum(self.model.requestInputLength), 0),
            func.coalesce(func.sum(self.model.outputLength), 0)
        ).where(
            self.model.userId == user_id,
            self.model.status == 1
        )

        # 动态添加时间过滤（今日统计 vs 历史总计复用）
        if start_time:
            stmt = stmt.where(self.model.createdAt >= start_time)
        if end_time:
            stmt = stmt.where(self.model.createdAt <= end_time)

        result = await self.db.execute(stmt)
        return result.one()  # 返回 (input_sum, output_sum)

    async def get_platform_usage_sum(self, start_time: datetime, end_time: datetime) -> int:
        """
        统计全平台在特定时间内的总 Token 消耗
        """
        stmt = select(
            func.coalesce(func.sum(self.model.requestInputLength + self.model.outputLength), 0)
        ).where(
            self.model.status == 1,
            self.model.createdAt >= start_time,
            self.model.createdAt <= end_time
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def create_ai_generate_log(self, log_obj: AiNovelGenerateLog):
        self.db.add(log_obj)
        await self.db.commit()  # 或者在 Service 层统一 commit