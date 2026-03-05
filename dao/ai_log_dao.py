from loguru import logger
from sqlalchemy import select, func, update, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import List, Tuple
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

    async def get_log_by_request_id(self, request_id: str) -> AiNovelGenerateLog:
        """
        根据 requestId 查询生成日志记录
        """
        # 使用 select 语句构建查询
        stmt = select(AiNovelGenerateLog).where(AiNovelGenerateLog.requestId == request_id)

        # 执行查询
        result = await self.db.execute(stmt)

        # 获取单个结果（如果没有则返回 None）
        return result.scalar_one_or_none()

    async def update_output_by_request_id(
            self,
            request_id: str,
            content: str,
            status: int = 1,
            error_msg: str = None
    ) -> bool:
        """
        根据 request_id 更新生成结果（适配驼峰命名字段）
        """
        try:
            # 计算长度，防止 content 为 None
            content_len = len(content) if content else 0

            # 构建更新语句
            # 注意：这里的 key 必须与 AiNovelGenerateLog 类中的属性名完全一致
            stmt = (
                update(AiNovelGenerateLog)
                .where(AiNovelGenerateLog.requestId == request_id)
                .values({
                    "outputContent": content,
                    "outputLength": content_len,
                    "status": status,
                    "errorMsg": error_msg,
                    "tokenEstimate": content_len // 2  # 按照你之前的逻辑：长度除以2
                })
            )

            result = await self.db.execute(stmt)
            # 在异步环境下，确保该 session 之后有 commit 操作
            # 如果你的 get_db_context() 不带自动 commit，这里需要手动调用：
            await self.db.commit()

            return result.rowcount > 0

        except Exception as e:
            # 这里的 logger 建议使用你项目配置好的
            logger.error(f"Update AiNovelGenerateLog Error: {e}")
            return False

    # 假设你的类名已统一为 AiNovelGenerateLog
    async def get_logs_by_bid(self, bid: str) -> List[dict]:
        """
        根据 bid (correlation) 获取生成日志列表
        只查询 originPrompt 和 request_id，优化内存占用
        """
        try:
            # 1. 明确指定查询列，避免加载 MEDIUMTEXT 字段
            stmt = (
                select(
                    AiNovelGenerateLog.requestId,
                    AiNovelGenerateLog.originPrompt,
                    AiNovelGenerateLog.createdAt
                )
                .where(AiNovelGenerateLog.bid == bid)  # 对应你改名后的字段
                .order_by(AiNovelGenerateLog.createdAt.desc())  # 按时间倒序，显示最新的
            )

            # 2. 执行查询
            result = await self.db.execute(stmt)

            # 3. 转换为字典列表返回，方便前端直接使用
            # 使用 mappings() 可以直接得到以列名为 key 的字典
            return result.mappings().all()

        except Exception as e:
            logger.error(f"Query AILog by bid error: {e}")
            return []

    async def get_logs_by_bid_paged(
            self,
            bid: str,
            page: int = 1,
            size: int = 10
    ) -> Tuple[List[dict], int]:
        """
        分页获取对话记录，仅查询轻量字段
        返回: (记录列表, 总条数)
        """
        try:
            # 1. 计算偏移量
            offset = (page - 1) * size

            # 2. 构建查询语句（只查询必要字段）
            # 注意：此处 correlation 对应你之前的 bid 改名
            stmt = (
                select(
                    AiNovelGenerateLog.requestId,
                    AiNovelGenerateLog.originPrompt,
                    AiNovelGenerateLog.status,
                    AiNovelGenerateLog.createdAt,
                    AiNovelGenerateLog.actionType
                )
                .where(and_(AiNovelGenerateLog.bid == bid, AiNovelGenerateLog.isDelete == 0))
                .order_by(desc(AiNovelGenerateLog.createdAt))
                .limit(size)
                .offset(offset)
            )

            # 3. 构建总数查询（用于前端分页插件）
            count_stmt = (
                select(func.count(AiNovelGenerateLog.id))
                .where(AiNovelGenerateLog.bid == bid)
            )

            # 4. 执行
            result = await self.db.execute(stmt)
            total_count = await self.db.scalar(count_stmt)

            # 转换为字典列表
            logs = result.mappings().all()
            return logs, total_count or 0

        except Exception as e:
            logger.error(f"分页查询 AI 日志失败: {e}")
            return [], 0

    @staticmethod
    async def logic_delete(
        db: AsyncSession,
        uid:int,
        request_ids: list
    ):
        """
        逻辑删除 AI 记录
        """

        stmt = (
            update(AiNovelGenerateLog)
            .where(and_(AiNovelGenerateLog.requestId.in_(request_ids),
                        AiNovelGenerateLog.userId == uid))
            .values(isDelete=1)
        )

        await db.execute(stmt)
        await db.commit()