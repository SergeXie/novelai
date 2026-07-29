from datetime import datetime
from typing import List, Tuple, Optional

from fastapi import params
from loguru import logger
from sqlalchemy import select, func, update, desc, and_, Integer, cast
from sqlalchemy.ext.asyncio import AsyncSession

from ai.adapters.enums import AIGenerateStatus
from core.entity.do.generate_log import AiNovelGenerateLog
from core.entity.do.generate_log_content import AiNovelGenerateLogContent
from core.entity.vo.ai_response import AICompletionResponse
from .base import BaseDAO


class AILogDAO(BaseDAO[AiNovelGenerateLog]):
    def __init__(self, db: AsyncSession):
        super().__init__(AiNovelGenerateLog, db)

    @staticmethod
    def _apply_content(
            log: AiNovelGenerateLog,
            content: AiNovelGenerateLogContent | None,
    ) -> AiNovelGenerateLog:
        """把新内容表字段装配回旧日志对象，保持上层接口字段不变。"""
        if content is None:
            return log

        log.userPrompt = content.user_prompt
        log.systemPrompt = content.system_prompt
        log.outputContent = content.output_content
        return log

    async def _get_content_by_request_id(
            self,
            request_id: str,
    ) -> AiNovelGenerateLogContent | None:
        result = await self.db.execute(
            select(AiNovelGenerateLogContent).where(
                AiNovelGenerateLogContent.request_id == request_id
            )
        )
        return result.scalar_one_or_none()

    async def _hydrate_logs_from_content(
            self,
            logs: List[AiNovelGenerateLog],
    ) -> List[AiNovelGenerateLog]:
        """批量读取内容表，并装配到日志对象的临时内容属性。"""
        if not logs:
            return logs

        request_ids = [log.requestId for log in logs]
        result = await self.db.execute(
            select(AiNovelGenerateLogContent).where(
                AiNovelGenerateLogContent.request_id.in_(request_ids)
            )
        )
        content_map = {
            item.request_id: item
            for item in result.scalars().all()
        }
        for log in logs:
            self._apply_content(log, content_map.get(log.requestId))
        return logs

    async def _upsert_output_content(
            self,
            request_id: str,
            output_content: str | None,
    ) -> bool:
        """更新新内容表输出；历史处理中日志没有内容行时自动补建。"""
        content = await self._get_content_by_request_id(request_id)
        if content is not None:
            content.output_content = output_content
            self.db.add(content)
            await self.db.flush()
            return True

        result = await self.db.execute(
            select(AiNovelGenerateLog).where(
                AiNovelGenerateLog.requestId == request_id
            )
        )
        log = result.scalar_one_or_none()
        if log is None:
            return False

        self.db.add(AiNovelGenerateLogContent(
            log_id=log.id,
            request_id=log.requestId,
            user_prompt=None,
            system_prompt=None,
            output_content=output_content,
        ))
        await self.db.flush()
        return True

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

    async def create_ai_generate_log(
            self,
            log_obj: AiNovelGenerateLog,
            user_prompt: str | None,
            system_prompt: str | None,
            output_content: str | None,
    ) -> AiNovelGenerateLog:
        """Create the lightweight log row and its one-to-one long-text content row."""
        self.db.add(log_obj)
        await self.db.flush()
        self.db.add(AiNovelGenerateLogContent(
            log_id=log_obj.id,
            request_id=log_obj.requestId,
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            output_content=output_content,
        ))
        await self.db.commit()
        await self.db.refresh(log_obj)

        log_obj.userPrompt = user_prompt
        log_obj.systemPrompt = system_prompt
        log_obj.outputContent = output_content
        return log_obj

    async def get_log_by_request_id(
            self,
            request_id: str,
            with_content: bool = True,
    ) -> AiNovelGenerateLog | None:
        """
        根据 requestId 查询生成日志记录。
        with_content=True 时同时装配内容表的大文本字段。
        """
        stmt = select(AiNovelGenerateLog).where(
            AiNovelGenerateLog.requestId == request_id
        )
        result = await self.db.execute(stmt)
        log = result.scalar_one_or_none()
        if log is None or not with_content:
            return log

        content = await self._get_content_by_request_id(request_id)
        return self._apply_content(log, content)

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
                   "outputLength": ai_rsp.usage.completion_tokens,
                   "requestInputLength": ai_rsp.usage.prompt_tokens,
                   "totalTokens": ai_rsp.usage.total_tokens,
               } if ai_rsp else {})
        }
        try:
            stmt = (
                update(AiNovelGenerateLog)
                .where(AiNovelGenerateLog.requestId == request_id)
                .values(update_fields)
            )
            result = await self.db.execute(stmt)
            if ai_rsp:
                await self._upsert_output_content(
                    request_id=request_id,
                    output_content=ai_rsp.content,
                )
            await self.db.flush()
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Dao update_output_by_request_id Transaction Failed: {e}")
            return False

    async def update_request_result_by_request_id(
            self,
            request_id: str,
            status: AIGenerateStatus,
            error_msg: str = "",
            output_content: str | None = None,
            output_length: int | None = None,
            request_input_length: int | None = None,
            total_tokens: int | None = None,
    ) -> bool:
        update_fields = {
            "status": status.value if hasattr(status, "value") else status,
            "errorMsg": error_msg,
        }

        if output_length is not None:
            update_fields["outputLength"] = output_length
        if request_input_length is not None:
            update_fields["requestInputLength"] = request_input_length
        if total_tokens is not None:
            update_fields["totalTokens"] = total_tokens

        try:
            stmt = (
                update(AiNovelGenerateLog)
                .where(AiNovelGenerateLog.requestId == request_id)
                .values(update_fields)
            )
            result = await self.db.execute(stmt)
            if output_content is not None:
                await self._upsert_output_content(
                    request_id=request_id,
                    output_content=output_content,
                )
            await self.db.flush()
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Dao update_request_result_by_request_id Transaction Failed: {e}")
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

    async def get_invalid_book_destructor_log(self, bid: str) -> AiNovelGenerateLog | None:
        """
        获取指定书籍最新的一条成功拆解记录 (status=1)
        注意：根据你模型中的 comment，成功状态是 1。
        如果你的业务逻辑中 2 代表特定的 '已完成' 状态，请保持 status=2。
        """
        try:
            # 1. 构造查询语句
            stmt = (
                select(AiNovelGenerateLog)
                .where(
                    AiNovelGenerateLog.bid == bid,
                    AiNovelGenerateLog.status == AIGenerateStatus.SUCCESS,  # 这里的状态码请根据你实际逻辑调整
                    AiNovelGenerateLog.isDelete == 0
                )
                # 2. 按照创建时间倒序排列，确保拿到的是最新的一条
                .order_by(desc(AiNovelGenerateLog.createdAt))
                # 3. 限制只取第一条
                .limit(1)
            )

            # 执行查询
            result = await self.db.execute(stmt)

            # scalars().first() 会返回对象本身，如果没有结果则返回 None
            log_entry = result.scalars().first()
            if log_entry is None:
                return None

            content = await self._get_content_by_request_id(log_entry.requestId)
            return self._apply_content(log_entry, content)

        except Exception as e:
            # 这里建议记录你的项目日志
            logger.error(f"查询拆书记录失败: {str(e)}")
            return None

    from sqlalchemy.ext.asyncio import AsyncSession

    async def sync_ai_log_data(self, source_request_id: str, target_request_id: str) -> Tuple[bool, str] :
        """
        将 source_log 的指定字段复制给 target_log 并更新
        """
        # 1. 获取源记录和目标记录
        source_log = await self.get_log_by_request_id(source_request_id)
        target_log = await self.get_log_by_request_id(target_request_id)

        if not source_log or not target_log:
            return False, "记录不存在"

        # 2. 定义需要同步的主表字段列表
        fields_to_copy = [
            "requestInputLength",
            "outputLength",
            "tokenEstimate",
            "status",
            "totalTokens"
        ]

        # 3. 执行复制
        for field in fields_to_copy:
            value = getattr(source_log, field)
            setattr(target_log, field, value)

        # The source content has been hydrated from the content table.
        await self._upsert_output_content(
            request_id=target_request_id,
            output_content=source_log.outputContent,
        )

        # 4. 提交到数据库
        try:
            await self.db.commit()
            return True, "更新成功"
        except Exception as e:
            await self.db.rollback()
            return False, f"更新失败: {str(e)}"

    async def get_logs_by_paged(
            self,
            user_id: Optional[int] = None,  # 修改为 int 类型提示
            bid: Optional[str] = None,
            page: int = 1,
            pageSize: int = 20,
            with_content: bool = False,
            start_time: Optional[datetime] = None,
            end_time: Optional[datetime] = None,
            origin_prompt: Optional[str] = None,
            action_type: Optional[str] = None,
    ) -> Tuple[list[AiNovelGenerateLog], int]:
        """
            获取排除大字段后的模型对象列表，并返回总数
            """
        try:
            offset = (page - 1) * pageSize

            # 1. 构造过滤条件
            filters = [AiNovelGenerateLog.isDelete == 0, AiNovelGenerateLog.totalTokens > 0]
            if user_id is not None:
                filters.append(AiNovelGenerateLog.userId == user_id)
            if bid:
                filters.append(AiNovelGenerateLog.bid == bid)
            if start_time:
                filters.append(AiNovelGenerateLog.createdAt >= start_time)
            if end_time:
                filters.append(AiNovelGenerateLog.createdAt <= end_time)
            if origin_prompt:
                origin_prompt = origin_prompt.strip()
                if origin_prompt:
                    filters.append(AiNovelGenerateLog.originPrompt.contains(origin_prompt, autoescape=True))
            if action_type:
                action_type = action_type.strip()
                if action_type:
                    filters.append(AiNovelGenerateLog.actionType == action_type)

            # The main log table no longer contains long-text content.
            stmt = (
                select(AiNovelGenerateLog)
                .where(and_(*filters))
                .order_by(desc(AiNovelGenerateLog.createdAt))
                .limit(pageSize)
                .offset(offset)
            )

            # 3. 查询总数
            count_stmt = (
                select(func.count(AiNovelGenerateLog.id))
                .where(and_(*filters))
            )

            # 4. 执行
            # 执行对象查询
            result = await self.db.execute(stmt)
            obj_list = list(result.scalars().all())
            if with_content:
                await self._hydrate_logs_from_content(obj_list)

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
        通过 offset_id 分页查询，并装配内容表字段
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
            # 4. 查询总数 (总数查询通常不带 id 过滤条件，除非是查剩余数量)
            count_filters = [AiNovelGenerateLog.isDelete == 0]
            if user_id is not None: count_filters.append(AiNovelGenerateLog.userId == user_id)
            if bid: count_filters.append(AiNovelGenerateLog.bid == bid)

            count_stmt = select(func.count(AiNovelGenerateLog.id)).where(and_(*count_filters))

            # 5. 执行
            result = await self.db.execute(stmt)
            # 转换为 list 确保数据被立刻读取到内存，避免 lazy load 风险
            obj_list = list(result.scalars().all())
            await self._hydrate_logs_from_content(obj_list)

            total_count = await self.db.scalar(count_stmt)

            return obj_list, total_count or 0

        except Exception as e:
            logger.error(f"分页查询 AI 日志失败 (user_id={user_id}, offset_id={offset_id}): {e}")
            return [], 0

    @staticmethod
    async def logic_delete(
            db: AsyncSession,
            uid: int,
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
    async def sum_free_tokens(
            db: AsyncSession,
            user_id: int,
            start_time: datetime,
            end_time: datetime | None = None,
    ) -> int:
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
        if end_time:
            stmt = stmt.where(AiNovelGenerateLog.createdAt < end_time)

        result = await db.execute(stmt)
        # scalar() 直接返回聚合后的单个数值
        return result.scalar() or 0
