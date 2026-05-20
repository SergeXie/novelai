from datetime import datetime, time

from dateutil import parser
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from ai.adapters.enums import AIAction, AIGenerateStatus
from common.config.config import settings
from core.entity.do.generate_log import AiNovelGenerateLog
from core.entity.vo.ai_model_vo import AIGenerateLogResp, AIGenerateLogDetailResp
from core.entity.vo.ai_response import AICompletionResponse, AIUserAssets
from core.entity.vo.base_vo import PageResp
from core.enums.token_consume_source import TokenConsumeSource
from dao.ai_log_dao import AILogDAO
from dao.ai_model_dao import AiModelDAO
from dao.user_account_dao import UserAccountDAO
from dao.user_dao import UserDAO


class UsageService:
    """AI 使用量相关服务。

    主要职责：
    1. 统计用户和平台的用量。
    2. 检查额度是否超限。
    3. 记录生成日志并提供历史查询。
    """

    def __init__(self, db: AsyncSession):
        self.ai_log_dao = AILogDAO(db)
        self.model_dao = AiModelDAO(db)
        self.db = db

    @staticmethod
    def get_today_range():
        """类内同名工具方法，作用和模块级 get_today_range 一样。"""
        today = datetime.now().date()
        start = datetime.combine(today, time.min)
        end = datetime.combine(today, time.max)
        return start, end

    @staticmethod
    def parse_query_time(value: str | None, is_end: bool = False) -> datetime | None:
        if not value:
            return None

        value = value.strip()
        parsed_time = parser.parse(value)

        if len(value) <= 10:
            return datetime.combine(parsed_time.date(), time.max if is_end else time.min)

        return parsed_time

    async def get_user_daily_input_output(self, user_id: int) -> tuple[int, int]:
        """获取用户今天累计的输入长度和输出长度。"""
        start, end = self.get_today_range()
        intput_count, output_count, _, _, _ = await self.ai_log_dao.get_usage_sum(user_id, start, end)
        return intput_count, output_count

    async def _get_user_daily_input_output(self, user_id: int) -> tuple[int, int]:
        """获取用户今天累计的输入长度和输出长度。"""
        start, end = self.get_today_range()
        intput_count, output_count, _, _, _ = await self.ai_log_dao._get_usage_sum(user_id, start, end)
        return intput_count, output_count

    async def get_user_total_input_output(self, user_id: int) -> tuple[int, int]:
        """获取用户历史累计的输入长度和输出长度。"""
        intput_total_count, output_total_count, actualAmount, freeDeduct, permanentDeduct = await self.ai_log_dao.get_usage_sum(user_id)
        return intput_total_count, output_total_count

    async def get_platform_daily_consumption(self):
        start, end = self.get_today_range()
        return await self.ai_log_dao.get_platform_usage_sum(start, end)

    async def record(
            self,
            user_id: int,
            level: int,
            bid: str,
            origin_prompt: str,
            request_id: str,
            system_prompt: str,
            user_prompt: str,
            temperature: float,
            output_content: str,
            node_ids : list = None,
            action_type: AIAction = AIAction.Generate,
            status=AIGenerateStatus.PENDING,
            promptTokens:int = 0,
            completionTokens:int = 0,
            totalTokens:int = 0,
            actualAmount:int = 0,
            consumeSource:TokenConsumeSource = TokenConsumeSource.FREE,
            freeDeduct:int = 0,
            monthlyDeduct:int = 0,
            permanentDeduct:int = 0,
            tokenEstimate: int = 0,
    ) -> AiNovelGenerateLog:
        """记录一次 AI 生成日志。

        会补充模型配置，并把输入、输出、估算 token、状态等信息一起入库。
        """
        # 根据等级找到对应模型，模型里通常带有倍率和 max_tokens 配置。
        ai_model_multiplier = 1
        max_tokens = 0
        model = await self.model_dao.get_model_by_level(level)
        model_name = "unknown"
        if model:
            ai_model_multiplier = model.multiplier
            max_tokens = model.max_tokens
            model_name = model.model_identifier

        if isinstance(action_type, str):
            action_type = AIAction(action_type)

        log = AiNovelGenerateLog(
            userId=user_id,
            requestId=request_id,
            bid=bid,
            node_ids=node_ids,
            originPrompt=origin_prompt,
            multiplier=ai_model_multiplier,
            # 输入信息
            userPrompt=user_prompt,
            systemPrompt=system_prompt,
            requestInputLength=promptTokens,
            model=model_name,
            temperature=temperature,
            maxTokens=max_tokens,
            # 输出信息
            outputContent=output_content,
            outputLength=completionTokens,
            # 这里只是粗略估算，不是严格 tokenizer 结果。
            tokenEstimate=tokenEstimate,
            actionType=action_type,
            status=status.value,
            totalTokens=totalTokens,
            actualAmount=actualAmount,
            consume_source=consumeSource,
            freeDeduct=freeDeduct,
            monthlyDeduct=monthlyDeduct,
            permanentDeduct=permanentDeduct,
        )
        return await self.ai_log_dao.create_ai_generate_log(log_obj=log)

    async def poll_content_by_request_id(self, request_id: str, user_id:int):
        """根据 request_id 查询生成内容，常用于前端轮询结果。"""
        log_record = await self.ai_log_dao.get_log_by_request_id(request_id=request_id)

        if log_record and log_record.userId == user_id:
            if log_record.status == AIGenerateStatus.SUCCESS:
                return log_record.outputContent
            elif log_record.status == AIGenerateStatus.FAILED:
                return "生成失败，请切换模型或者稍后重试"

        return ""

    async def get_book_invalid_destructor_log(self, bid: str):
        """获取指定书籍最近一条可复用的拆书记录。"""
        return await self.ai_log_dao.get_invalid_book_destructor_log(bid=bid)

    async def get_log_by_request_id(self, request_id: str) -> AiNovelGenerateLog | None:
        return await self.ai_log_dao.get_log_by_request_id(request_id=request_id)

    async def update_output_content_by_request_id(
            self,
            request_id: str,
            ai_rsp: AICompletionResponse | None,
            status: AIGenerateStatus = AIGenerateStatus.SUCCESS,
            error_msg: str = ""
    )->bool:
        """根据 request_id 更新生成后的输出内容。"""
        if not request_id:
            return False

        success = await self.ai_log_dao.update_output_by_request_id(
            request_id=request_id,
            ai_rsp=ai_rsp,
            status=status,
            error_msg=error_msg
        )

        if status == AIGenerateStatus.SUCCESS and ai_rsp:
            await self.record_consumption(request_id=request_id, total_tokens=ai_rsp.usage.total_tokens, multiplier=settings.MULTIPLIER)

        if success:
            logger.info(f"RequestId: {request_id} 内容更新成功")
        else:
            logger.error(f"RequestId: {request_id} 内容更新失败")

        return success

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
        if not request_id:
            return False

        success = await self.ai_log_dao.update_request_result_by_request_id(
            request_id=request_id,
            status=status,
            error_msg=error_msg,
            output_content=output_content,
            output_length=output_length,
            request_input_length=request_input_length,
            total_tokens=total_tokens,
        )

        if success:
            logger.info(f"RequestId: {request_id} 请求结果更新成功")
        else:
            logger.error(f"RequestId: {request_id} 请求结果更新失败")

        return success

    async def update_image_output_by_request_id(
            self,
            request_id: str,
            image_url: str,
            status: AIGenerateStatus = AIGenerateStatus.SUCCESS,
            error_msg: str = "",
    ) -> bool:
        return await self.update_request_result_by_request_id(
            request_id=request_id,
            status=status,
            error_msg=error_msg,
            output_content=image_url,
            output_length=len(image_url),
        )

    async def get_book_chat_history(self, bid: str, page: int, size: int, with_content:bool = False) -> PageResp:
        """分页获取某本书下的 AI 对话历史。"""
        logs, total = await self.ai_log_dao.get_logs_by_paged(bid=bid, page=page, pageSize=size, with_content=with_content)

        list_data = [
            await AIGenerateLogResp.from_orm_model(log, self.model_dao)
            for log in logs
        ]

        return PageResp(
            list=list_data,
            total=total,
            page=page,
            pageSize=size
        )

    async def get_invalid_book_destructor_log(self, bid: str) -> AiNovelGenerateLog | None:
        return await self.ai_log_dao.get_invalid_book_destructor_log(bid=bid)

    async def get_chat_history(self, bid: str, offset_id: int, size: int, with_content:bool = False, user_id: int | None = None) -> PageResp:
        """分页获取某本书下的 AI 对话历史。"""
        logs, total = await self.ai_log_dao.get_full_logs_by_offset(user_id=user_id, bid=bid, offset_id=offset_id, size=size)

        list_data = [
            await AIGenerateLogResp.from_orm_model(log, self.model_dao)
            for log in logs
        ]

        return PageResp(
            list=list_data,
            total=total,
            page=-1,
            pageSize=size
        )

    async def get_logs_page(
            self,
            user_id: int,
            page: int,
            pageSize: int,
            start_time: str | None = None,
            end_time: str | None = None,
            origin_prompt: str | None = None,
    ):
        start_time = self.parse_query_time(start_time)
        end_time = self.parse_query_time(end_time, is_end=True)

        logs, total = await self.ai_log_dao.get_logs_by_paged(
            user_id=user_id,
            page=page,
            pageSize=pageSize,
            start_time=start_time,
            end_time=end_time,
            origin_prompt=origin_prompt,
        )

        list_data = [
            await AIGenerateLogResp.from_orm_model(log, self.model_dao)
            for log in logs
        ]

        # 3. 返回标准分页模型
        return PageResp(
            list=list_data,
            total=total,
            page=page,
            pageSize=pageSize
        )

    async def get_log_detail(self, request_id: str) -> AIGenerateLogDetailResp:
        log = await self.ai_log_dao.get_log_by_request_id(request_id=request_id)
        return await AIGenerateLogDetailResp.from_orm_model(log, self.model_dao) if log else None

    async def get_user_assets(self, user_id: int) -> AIUserAssets:
        # 1. 从 DB 或 Redis 获取静态余额 (假设 account 是 UserAccount 对象)
        account = await UserAccountDAO.get_active_account(db=self.db, user_id=user_id)

        # 2. 调用之前的 LogDAO 统计今日消耗
        today_start = datetime.combine(datetime.now().date(), time.min)
        used_tokens = await AILogDAO.sum_free_tokens(self.db, user_id=user_id, start_time=today_start)

        # 3. 转化为 BaseModel 返回
        return AIUserAssets(
            daily_limit=settings.USER_DAILY_TOKEN_LIMIT,
            used_free=used_tokens,
            monthly_balance=account.monthly_balance if account.monthly_balance else 0,
            permanent_balance=account.permanent_balance if account.permanent_balance else 0,
        )

    async def record_consumption(
            self,
            request_id: str,
            total_tokens: int,
            multiplier: float
    ):
        """
        执行实际扣减并回填日志
        优先级：免费额度 (Daily Free) -> 月度额度 (Monthly) -> 永久额度 (Permanent)
        """
        # 1. 获取日志对象
        log_entry: AiNovelGenerateLog = await self.ai_log_dao.get_log_by_request_id(request_id=request_id)
        if log_entry is None:
            logger.error(f"未找到对应的请求日志: {request_id}")
            return

        user_id = log_entry.userId

            # 计算总计费点数
        actual_amount = int(total_tokens * multiplier)
        log_entry.totalTokens = total_tokens
        log_entry.actualAmount = actual_amount

        # 2. 查询用户当前所有资产
        account = await UserAccountDAO.get_active_account(db=self.db, user_id=user_id)

        remaining_to_pay = actual_amount

        # --- 资产拆解扣减逻辑 (顺序调整) ---

        # A. 【首先】抵扣每日免费额度 (Free)
        # 注意：免费额度通常由 settings.USER_DAY_LIMIT 减去 今日已用 算出
        # 假设你的 check_quota 逻辑里已经算过了，这里我们需要知道用户今天还能免单多少
        input_total, output_total = await self.get_user_daily_input_output(user_id)
        user_already_used_weighted = int((input_total + output_total) * multiplier)
        # 计算今天剩余可用的免费额度
        free_limit_remaining = max(0, settings.USER_DAILY_TOKEN_LIMIT - user_already_used_weighted)
        print("本次使用的额度：{}".format(remaining_to_pay))
        if free_limit_remaining > 0 and remaining_to_pay > 0:
            free_deduct = min(free_limit_remaining, remaining_to_pay)
            log_entry.freeDeduct = free_deduct
            remaining_to_pay -= free_deduct
            # 免费额度是虚拟限额，不需要在 account 表里减扣，只需记录在 log
            logger.info("免费额度：{}".format(free_limit_remaining))

        # B. 【其次】抵扣月度额度 (Monthly)
        if account and account.monthly_balance > 0 and remaining_to_pay > 0:
            monthly_deduct = min(account.monthly_balance, remaining_to_pay)
            log_entry.monthlyDeduct = monthly_deduct
            account.monthly_balance -= monthly_deduct
            account.total_consumed += monthly_deduct
            remaining_to_pay -= monthly_deduct
            logger.info("抵扣月度额度")
            await self.consume_tokens(account, actual_amount, user_id, request_id)


        # C. 【最后】抵扣永久额度 (Permanent)
        if account and account.permanent_balance > 0 and remaining_to_pay > 0:
            perm_deduct = min(account.permanent_balance, remaining_to_pay)
            log_entry.permanentDeduct = perm_deduct
            account.permanent_balance -= perm_deduct
            account.total_consumed += perm_deduct
            remaining_to_pay -= perm_deduct
            logger.info("抵扣永久额度")
            await self.consume_tokens(account, actual_amount, user_id, request_id)

        # --- 3. 核心修正：判定 TokenConsumeSource ---

        # 统计有多少种资产被动用了
        used_sources_count = sum([
            1 if log_entry.freeDeduct > 0 else 0,
            1 if log_entry.monthlyDeduct > 0 else 0,
            1 if log_entry.permanentDeduct > 0 else 0
        ])

        if used_sources_count > 1:
            log_entry.consume_source = TokenConsumeSource.MIXED
        elif log_entry.freeDeduct > 0:
            log_entry.consume_source = TokenConsumeSource.FREE
        elif log_entry.monthlyDeduct > 0:
            log_entry.consume_source = TokenConsumeSource.MEMBER_MONTHLY
        elif log_entry.permanentDeduct > 0:
            log_entry.consume_source = TokenConsumeSource.PERMANENT
        else:
            # 兜底：如果产生 0 token 消耗或异常
            log_entry.consume_source = TokenConsumeSource.FREE

        # 4. 提交数据库
        # 记得更新 account 表的相关余额
        await self.db.commit()

    async def consume_tokens(self, account, actual_amount, user_id, request_id):
        # 新增额外流水
        consume_monthly = min(account.monthly_balance, actual_amount)
        consume_permanent = actual_amount - consume_monthly
        await UserDAO.create_log(
            db=self.db,
            user_id=user_id,
            request_id=request_id,
            monthly_amount=consume_monthly,
            permanent_amount=consume_permanent,
            total_amount=actual_amount,
            balance_snapshot={
                "monthly": account.monthly_balance,
                "permanent": account.permanent_balance
            }
        )

        logger.info(
            f"[扣费] 成功 user_id={user_id}, monthly={consume_monthly}, permanent={consume_permanent}"
        )
