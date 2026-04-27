from datetime import datetime
from typing import List, Tuple, Optional

from fastapi import params
from loguru import logger
from sqlalchemy import select, func, update, desc, and_, Integer, cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer, defer

from ai.adapters.enums import AIGenerateStatus
from core.entity.do.generate_log import AiNovelGenerateLog
from core.entity.vo.ai_response import AICompletionResponse
from .base import BaseDAO


class AILogDAO(BaseDAO[AiNovelGenerateLog]):
    def __init__(self, db: AsyncSession):
        super().__init__(AiNovelGenerateLog, db)

    async def get_usage_sum(self,
                            user_id: int,
                            start_time: datetime = None,
                            end_time: datetime = None) -> Tuple[int, int, int, int, int]:
        """
        高效统计：利用索引下推减少内存扫描，并处理空值。
        """
        # 1. 预构建聚合列，增加别名方便调试
        metrics = [
            func.coalesce(cast(func.sum(self.model.requestInputLength), Integer), 0).label("in_len"),
            func.coalesce(cast(func.sum(self.model.outputLength), Integer), 0).label("out_len"),
            func.coalesce(cast(func.sum(self.model.actualAmount), Integer), 0).label("total"),
            func.coalesce(cast(func.sum(self.model.freeDeduct), Integer), 0).label("free"),
            func.coalesce(cast(func.sum(self.model.permanentDeduct), Integer), 0).label("perm")
        ]

        # 2. 构造查询：务必确保 userId 和 createdAt 组合索引被激活
        stmt = select(*metrics).where(
            self.model.userId == user_id,
            self.model.status == 1,
            self.model.isDelete == 0  # 增加逻辑删除过滤，避免统计无效数据
        )

        if start_time:
            stmt = stmt.where(self.model.createdAt >= start_time)
        if end_time:
            stmt = stmt.where(self.model.createdAt <= end_time)

        # 3. 使用 execute().one() 的安全解包
        # 4G 服务器建议：使用 scalars 或 row 结果前先检查
        try:
            result = await self.db.execute(stmt)
            row = result.one()
            return tuple(row)
        except Exception as e:
            logger.error(f"Usage sum failed for user {user_id}: {e}")
            return 0, 0, 0, 0, 0

    async def _get_usage_sum(self,
                            user_id: int,
                            start_time: datetime = None,
                            end_time: datetime = None) -> Tuple[int, int, int, int, int]:
        """
        高效统计：利用索引下推减少内存扫描，并处理空值。
        """
        # 1. 预构建聚合列，增加别名方便调试
        metrics = [
            func.coalesce(cast(func.sum(self.model.requestInputLength), Integer), 0).label("in_len"),
            func.coalesce(cast(func.sum(self.model.outputLength), Integer), 0).label("out_len"),
            func.coalesce(cast(func.sum(self.model.actualAmount), Integer), 0).label("total"),
            func.coalesce(cast(func.sum(self.model.freeDeduct), Integer), 0).label("free"),
            func.coalesce(cast(func.sum(self.model.permanentDeduct), Integer), 0).label("perm")
        ]

        # 2. 构造查询：务必确保 userId 和 createdAt 组合索引被激活
        stmt = select(*metrics).where(
            self.model.userId == user_id,
            self.model.status == 2,
            self.model.isDelete == 0  # 增加逻辑删除过滤，避免统计无效数据
        )

        if start_time:
            stmt = stmt.where(self.model.createdAt >= start_time)
        if end_time:
            stmt = stmt.where(self.model.createdAt <= end_time)

        # 3. 使用 execute().one() 的安全解包
        # 4G 服务器建议：使用 scalars 或 row 结果前先检查
        try:
            result = await self.db.execute(stmt)
            row = result.one()
            return tuple(row)
        except Exception as e:
            logger.error(f"Usage sum failed for user {user_id}: {e}")
            return 0, 0, 0, 0, 0

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

    async def create_ai_generate_log(self, log_obj: AiNovelGenerateLog) -> AiNovelGenerateLog:
        self.db.add(log_obj)
        await self.db.commit()
        await self.db.refresh(log_obj)
        return log_obj

    async def get_log_by_request_id(self, request_id: str) -> AiNovelGenerateLog:
        """
        根据 requestId 查询生成日志记录
        """
        # 使用 select 语句构建查询
        stmt = select(AiNovelGenerateLog).where(AiNovelGenerateLog.requestId == request_id).options(
            # 显式取消延迟加载，确保详情页能拿到完整内容
            undefer(AiNovelGenerateLog.outputContent),
            undefer(AiNovelGenerateLog.systemPrompt),
            undefer(AiNovelGenerateLog.userPrompt)
        )

        # 执行查询
        result = await self.db.execute(stmt)

        # 获取单个结果（如果没有则返回 None）
        return result.scalar_one_or_none()

    async def update_output_by_request_id(
            self,
            request_id: str,
            ai_rsp: AICompletionResponse,
            status: AIGenerateStatus = AIGenerateStatus.SUCCESS,
            error_msg: str = ""
    ) -> bool:
        """
        根据 request_id 更新生成结果（适配驼峰命名字段）
        更新生成结果 + 扣Token
        """
        update_fields = {
            "status": status.value if hasattr(status, "value") else status,
            "errorMsg": error_msg,
            **({
                   "outputContent": ai_rsp.content,
                   "outputLength": ai_rsp.usage.completion_tokens,
                   "requestInputLength": ai_rsp.usage.prompt_tokens,
                   "totalTokens": ai_rsp.usage.total_tokens,
               } if ai_rsp else {})
        }
        try:
            async with self.db.begin():
                stmt = (
                    update(AiNovelGenerateLog)
                    .where(AiNovelGenerateLog.requestId == request_id)
                    .values(update_fields)
                )
                result = await self.db.execute(stmt)
                return result.rowcount > 0
        except Exception as e:
            logger.error(f"Dao update_output_by_request_id Transaction Failed: {e}")
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

    async def get_logs_by_paged(
            self,
            user_id: Optional[int] = None,  # 修改为 int 类型提示
            bid: Optional[str] = None,
            page: int = 1,
            size: int = 10,
            with_content: bool = False
    ) -> Tuple[list[AiNovelGenerateLog], int]:
        """
            获取排除大字段后的模型对象列表，并返回总数
            """
        try:
            offset = (page - 1) * size

            # 1. 构造过滤条件
            filters = [AiNovelGenerateLog.isDelete == 0]
            if user_id is not None:
                filters.append(AiNovelGenerateLog.userId == user_id)
            if bid:
                filters.append(AiNovelGenerateLog.bid == bid)

            # 2. 查询对象列表（使用 defer 排除所有 LongText 字段）
            # 这样加载到内存中的对象非常轻量
            stmt = (
                select(AiNovelGenerateLog)
                .where(and_(*filters))
                .order_by(desc(AiNovelGenerateLog.createdAt))
                .limit(size)
                .offset(offset)
            )

            # --- 核心逻辑：动态处理 content 字段 ---
            if not with_content:
                # 如果不需要内容，则延迟加载 content 字段
                # 注意：你可以根据需要 defer 多个大字段，如 .options(defer(Model.col1), defer(Model.col2))
                stmt = stmt.options(defer(AiNovelGenerateLog.outputContent))

            # 3. 查询总数
            count_stmt = (
                select(func.count(AiNovelGenerateLog.id))
                .where(and_(*filters))
            )

            # 4. 执行
            # 执行对象查询
            result = await self.db.execute(stmt)
            obj_list = result.scalars().all()  # 这里得到的是 List[AiNovelGenerateLog]

            # 执行计数查询
            total_count = await self.db.scalar(count_stmt)

            return obj_list, total_count or 0

        except Exception as e:
            logger.error(f"分页查询 AI 日志失败 (user_id={user_id}, bid={bid}): {e}")
            return [], 0

    async def get_full_logs_by_offset(
            self,
            user_id: Optional[int] = None,
            bid: Optional[str] = None,
            offset_id: int = 0,  # 基于 ID 的游标起始点
            size: int = 10
    ) -> Tuple[List[AiNovelGenerateLog], int]:
        """
        通过 offset_id 分页查询，并包含 outputContent 字段
        """
        try:
            # 1. 构造基础过滤条件
            filters = [AiNovelGenerateLog.isDelete == 0]

            # 2. 添加 offset_id 过滤 (游标分页核心)
            if offset_id > 0:
                filters.append(AiNovelGenerateLog.id < offset_id)  # 假设你是按时间倒序查，则 ID 应小于当前 ID

            if user_id is not None:
                filters.append(AiNovelGenerateLog.userId == user_id)
            if bid:
                filters.append(AiNovelGenerateLog.bid == bid)

            # 3. 构造查询语句
            stmt = (
                select(AiNovelGenerateLog)
                .where(and_(*filters))
                .order_by(desc(AiNovelGenerateLog.id))  # 使用 ID 排序比使用 createdAt 性能更稳
                .limit(size)
            )
            stmt = stmt.options(
                undefer(AiNovelGenerateLog.outputContent),
                undefer(AiNovelGenerateLog.userPrompt)
            )

            # 注意：这里去掉了 if not with_content 的 defer 逻辑
            # outputContent 会被自然地 select 出来

            # 4. 查询总数 (总数查询通常不带 id 过滤条件，除非是查剩余数量)
            count_filters = [AiNovelGenerateLog.isDelete == 0]
            if user_id is not None: count_filters.append(AiNovelGenerateLog.userId == user_id)
            if bid: count_filters.append(AiNovelGenerateLog.bid == bid)

            count_stmt = select(func.count(AiNovelGenerateLog.id)).where(and_(*count_filters))

            # 5. 执行
            result = await self.db.execute(stmt)
            # 转换为 list 确保数据被立刻读取到内存，避免 lazy load 风险
            obj_list = list(result.scalars().all())

            total_count = await self.db.scalar(count_stmt)

            return obj_list, total_count or 0

        except Exception as e:
            logger.error(f"分页查询 AI 日志失败 (user_id={user_id}, offset_id={offset_id}): {e}")
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

    @staticmethod
    async def sum_free_tokens(db: AsyncSession, user_id: int, start_time: datetime) -> int:
        """
        统计指定用户自 start_time 以来消耗的免费 Token 总数
        """
        # 构建查询语句
        stmt = (
            select(
                # 使用 func.coalesce 确保没有记录时返回 0 而不是 None
                func.coalesce(func.sum(AiNovelGenerateLog.freeDeduct), 0)
            )
            .where(
                and_(
                    AiNovelGenerateLog.userId == user_id,
                    # 仅统计成功或处理中的记录（处理中代表已预扣）
                    AiNovelGenerateLog.status.in_([
                        AIGenerateStatus.SUCCESS,
                        AIGenerateStatus.PROCESSING
                    ]),
                    # 时间范围过滤（通常是今日零点之后）
                    AiNovelGenerateLog.createdAt >= start_time,
                    # 逻辑删除过滤
                    AiNovelGenerateLog.isDelete == 0
                )
            )
        )

        # 执行查询
        result = await db.execute(stmt)
        # scalar() 直接返回聚合后的单个数值
        return result.scalar() or 0