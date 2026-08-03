from datetime import datetime, time
from decimal import Decimal, ROUND_CEILING
from typing import Optional

from dateutil import parser
from dateutil.relativedelta import relativedelta
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
from service.account_service import AccountService
from service.redeem_code_service import RedeemCodeService


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
    def get_month_range():
        today = datetime.now().date()
        start = datetime.combine(today.replace(day=1), time.min)
        end = start + relativedelta(months=1)
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

    @staticmethod
    def calculate_model_price_amount(
            prompt_tokens: int,
            completion_tokens: int,
            input_price,
            output_price,
            sale_multiplier,
    ) -> int:
        """
        按模型人民币成本价计算文墨值扣费。

        input_price/output_price 是每 100 万 Token 的人民币成本价；
        产品定价是 15 元 = 1,000,000 文墨值，所以可化简为：
        (输入Token * 输入单价 + 输出Token * 输出单价) * 售价倍率 / 15
        """
        prompt = Decimal(max(0, prompt_tokens or 0))
        completion = Decimal(max(0, completion_tokens or 0))
        input_unit_price = Decimal(str(input_price or 0))
        output_unit_price = Decimal(str(output_price or 0))
        price_multiplier = Decimal(str(sale_multiplier or 5))

        if input_unit_price <= 0 and output_unit_price <= 0:
            return 0

        amount = (
            (prompt * input_unit_price + completion * output_unit_price)
            * price_multiplier
            / Decimal("15")
        )
        return int(amount.to_integral_value(rounding=ROUND_CEILING))

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

    async def get_user_monthly_input_output(self, user_id: int) -> tuple[int, int]:
        start, end = self.get_month_range()
        intput_count, output_count, _, _, _ = await self.ai_log_dao.get_usage_sum(user_id, start, end)
        return intput_count, output_count

    async def get_user_monthly_free_used(self, user_id: int) -> int:
        account = await UserAccountDAO.get_active_account(db=self.db, user_id=user_id)
        if not account:
            account = await AccountService.init_account(self.db, user_id)
        await AccountService.ensure_monthly_free_allowance(self.db, account)
        return max(0, (account.free_total_amount or 0) - (account.free_balance or 0))

    async def get_user_monthly_free_remaining(self, user_id: int) -> int:
        account = await UserAccountDAO.get_active_account(db=self.db, user_id=user_id)
        if not account:
            account = await AccountService.init_account(self.db, user_id)
        await AccountService.ensure_monthly_free_allowance(self.db, account)
        return max(0, account.free_balance or 0)

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
            template_key: str | None = None,
            action_type: AIAction = AIAction.Generate,
            status=AIGenerateStatus.PENDING,
            promptTokens:int = 0,
            completionTokens:int = 0,
            totalTokens:int = 0,
            actualAmount:int = 0,
            consumeSource:TokenConsumeSource = TokenConsumeSource.FREE,
            freeDeduct:int = 0,
            monthlyDeduct:int = 0,
            bonusDeduct:int = 0,
            permanentDeduct:int = 0,
            tokenEstimate: int = 0,
            max_tokens: int | None = None,
    ) -> AiNovelGenerateLog:
        """记录一次 AI 生成日志。

        会补充模型配置，并把输入、输出、估算 token、状态等信息一起入库。
        """
        # 根据等级找到对应模型，模型里通常带有倍率和 max_tokens 配置。
        ai_model_multiplier = 1
        model_max_tokens = 0
        model = await self.model_dao.get_model_by_level(level)
        model_name = "unknown"
        if model:
            ai_model_multiplier = model.multiplier
            model_max_tokens = model.max_tokens
            model_name = model.model_identifier
        # 优先使用调用方传入的 max_tokens，回退到模型默认值
        final_max_tokens = max_tokens if max_tokens is not None else model_max_tokens

        if isinstance(action_type, str):
            action_type = AIAction(action_type)

        log = AiNovelGenerateLog(
            userId=user_id,
            requestId=request_id,
            bid=bid,
            node_ids=node_ids,
            template_key=template_key,
            originPrompt=origin_prompt,
            multiplier=ai_model_multiplier,
            requestInputLength=promptTokens,
            model=model_name,
            temperature=temperature,
            maxTokens=final_max_tokens,
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
            bonusDeduct=bonusDeduct,
            permanentDeduct=permanentDeduct,
        )
        return await self.ai_log_dao.create_ai_generate_log(
            log_obj=log,
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            output_content=output_content,
        )

    async def poll_content_by_request_id(self, request_id: str, user_id:int):
        """根据 request_id 查询生成内容，常用于前端轮询结果。"""
        log_record = await self.ai_log_dao.get_log_by_request_id(request_id=request_id)

        if log_record and log_record.userId == user_id:
            if log_record.status == AIGenerateStatus.SUCCESS:
                return log_record.outputContent
            elif log_record.status == AIGenerateStatus.FAILED:
                # 仅透出已确认可面向用户展示的业务校验提示；模型原始异常仍使用通用文案。
                if log_record.errorMsg == "当前输入内容较长，已超过该模型的处理上限，请精简内容后重试或切换模型。":
                    return log_record.errorMsg
                return "生成失败，请切换模型或者稍后重试"

        return ""

    async def get_book_invalid_destructor_log(self, bid: str):
        """获取指定书籍最近一条可复用的拆书记录。"""
        return await self.ai_log_dao.get_invalid_book_destructor_log(bid=bid)

    async def get_log_by_request_id(
            self,
            request_id: str,
            with_content: bool = True,
    ) -> AiNovelGenerateLog | None:
        return await self.ai_log_dao.get_log_by_request_id(
            request_id=request_id,
            with_content=with_content,
        )

    async def update_output_content_by_request_id(
            self,
            request_id: str,
            ai_rsp: Optional[AICompletionResponse],
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
            await self.record_consumption(
                request_id=request_id,
                total_tokens=ai_rsp.usage.total_tokens,
                multiplier=settings.MULTIPLIER,
                prompt_tokens=ai_rsp.usage.prompt_tokens,
                completion_tokens=ai_rsp.usage.completion_tokens,
            )

        if success:
            display_content = ""
            if ai_rsp:
                display_content = ai_rsp.content[:20] + "..." if len(ai_rsp.content) > 20 else ai_rsp.content
            logger.info(f"RequestId: {request_id} 内容更新成功 :{display_content}")
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
        success = await self.update_request_result_by_request_id(
            request_id=request_id,
            status=status,
            error_msg=error_msg,
            output_content=image_url,
            output_length=settings.IMAGE_GENERATE_TOKEN_COST,  # 文生图通常按单次固定 token 计算
            total_tokens=settings.IMAGE_GENERATE_TOKEN_COST,  # 文生图通常按单次固定 token计算
        )
        if success and status == AIGenerateStatus.SUCCESS:
            await self.record_consumption(
                request_id=request_id,
                total_tokens=settings.IMAGE_GENERATE_TOKEN_COST,
                multiplier=settings.MULTIPLIER
            )
        return success

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
            action_type: str | None = None,
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
            action_type=action_type,
        )

        list_data = []
        for log in logs:
            resp_obj = await AIGenerateLogResp.from_orm_model(log, self.model_dao)
            resp_obj.totalTokens = int(log.actualAmount or 0)
            list_data.append(resp_obj)

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
        if not account:
            account = await AccountService.init_account(self.db, user_id)
        await AccountService.ensure_monthly_free_allowance(self.db, account)

        # 2. 调用之前的 LogDAO 统计今日消耗
        free_total = account.free_total_amount or 0
        free_balance = account.free_balance or 0

        # 3. 转化为 BaseModel 返回
        return AIUserAssets(
            daily_limit=free_total,
            used_free=max(0, free_total - free_balance),
            monthly_balance=account.monthly_balance if account.monthly_balance else 0,
            bonus_balance=account.bonus_balance if account.bonus_balance else 0,
            permanent_balance=account.permanent_balance if account.permanent_balance else 0,
        )

    async def record_consumption(
            self,
            request_id: str,
            total_tokens: int,
            multiplier: float,
            prompt_tokens: int | None = None,
            completion_tokens: int | None = None,
    ):
        """
        执行实际扣减并回填日志
        文本生成按“输入 Token 50% + 输出 Token 100%”计算计费额度；
        prompt_tokens = 输入 Token
        completion_tokens = 输出 Token
        totalTokens、requestInputLength、outputLength 仍记录模型返回的原始用量。
        优先级：免费额度 (Daily Free) -> 月度额度 (Monthly) -> 永久额度 (Permanent)
        """
        # 1. 获取日志对象
        log_entry: AiNovelGenerateLog = await self.ai_log_dao.get_log_by_request_id(
            request_id=request_id,
            with_content=False,
        )
        if log_entry is None:
            logger.error(f"未找到对应的请求日志: {request_id}")
            return

        user_id = log_entry.userId

        model = await self.model_dao.get_model_by_identifier(log_entry.model)
        actual_amount = 0

        # 新模型价格计费：只使用 input_price/output_price/sale_multiplier。
        # 不再叠加全局倍率 settings.MULTIPLIER，也不再叠加旧模型倍率 multiplier。
        if model:
            actual_amount = self.calculate_model_price_amount(
                prompt_tokens=prompt_tokens or 0,
                completion_tokens=completion_tokens if completion_tokens is not None else total_tokens,
                input_price=getattr(model, "input_price", 0),
                output_price=getattr(model, "output_price", 0),
                sale_multiplier=getattr(model, "sale_multiplier", 5),
            )

        if not model:
            # 找不到模型配置时，只按固定额度原值兜底，不再乘任何倍率。
            actual_amount = int(max(0, total_tokens))

        asset_amount = actual_amount
        log_entry.totalTokens = total_tokens
        log_entry.actualAmount = actual_amount

        # 2. 查询用户当前所有资产
        account = await UserAccountDAO.get_active_account(db=self.db, user_id=user_id)
        if not account:
            account = await AccountService.init_account(self.db, user_id)
        await AccountService.ensure_monthly_free_allowance(self.db, account)

        remaining_to_pay = asset_amount

        # --- 资产拆解扣减逻辑 (顺序调整) ---

        # A. 【首先】抵扣本月免费额度 (Free)
        # 免费额度已经作为账户资产发放到 free_balance，这里按余额真实扣减。
        free_balance = account.free_balance if account else 0
        if free_balance > 0 and remaining_to_pay > 0:
            free_deduct = min(free_balance, remaining_to_pay)
            log_entry.freeDeduct = free_deduct
            account.free_balance -= free_deduct
            account.total_consumed += free_deduct
            remaining_to_pay -= free_deduct
            logger.info("抵扣基础免费额度")

        # B. 【其次】抵扣补给奖励额度 (Bonus)
        if account and account.bonus_balance > 0 and remaining_to_pay > 0:
            bonus_deduct = min(account.bonus_balance, remaining_to_pay)
            log_entry.bonusDeduct = bonus_deduct
            account.bonus_balance -= bonus_deduct
            account.total_consumed += bonus_deduct
            remaining_to_pay -= bonus_deduct
            logger.info("抵扣补给奖励额度")


        redeem_deduct = 0
        if account and account.redeem_balance > 0 and remaining_to_pay > 0:
            redeem_deduct = await RedeemCodeService.consume_redeem_balance(self.db, account, remaining_to_pay)
            remaining_to_pay -= redeem_deduct
            if redeem_deduct > 0:
                logger.info("抵扣兑换码额度")
        # C. 【再次】抵扣月度额度 (Monthly)
        if account and account.monthly_balance > 0 and remaining_to_pay > 0:
            monthly_deduct = min(account.monthly_balance, remaining_to_pay)
            log_entry.monthlyDeduct = monthly_deduct
            account.monthly_balance -= monthly_deduct
            account.total_consumed += monthly_deduct
            remaining_to_pay -= monthly_deduct
            logger.info("抵扣月度额度")

        # D. 【最后】抵扣永久额度 (Permanent)
        if account and account.permanent_balance > 0 and remaining_to_pay > 0:
            perm_deduct = min(account.permanent_balance, remaining_to_pay)
            log_entry.permanentDeduct = perm_deduct
            account.permanent_balance -= perm_deduct
            account.total_consumed += perm_deduct
            remaining_to_pay -= perm_deduct
            logger.info("抵扣永久额度")

        if account:
            await self.consume_tokens(
                account=account,
                actual_amount=asset_amount,
                user_id=user_id,
                request_id=request_id,
                free_amount=log_entry.freeDeduct,
                monthly_amount=log_entry.monthlyDeduct,
                bonus_amount=log_entry.bonusDeduct,
                redeem_amount=redeem_deduct,
                permanent_amount=log_entry.permanentDeduct,
            )

        # --- 3. 核心修正：判定 TokenConsumeSource ---

        # 统计有多少种资产被动用了
        used_sources_count = sum([
            1 if log_entry.freeDeduct > 0 else 0,
            1 if log_entry.monthlyDeduct > 0 else 0,
            1 if log_entry.bonusDeduct > 0 else 0,
            1 if redeem_deduct > 0 else 0,
            1 if log_entry.permanentDeduct > 0 else 0
        ])

        if used_sources_count > 1:
            log_entry.consume_source = TokenConsumeSource.MIXED
        elif log_entry.freeDeduct > 0:
            log_entry.consume_source = TokenConsumeSource.FREE
        elif log_entry.monthlyDeduct > 0:
            log_entry.consume_source = TokenConsumeSource.MEMBER_MONTHLY
        elif log_entry.bonusDeduct > 0:
            log_entry.consume_source = TokenConsumeSource.BONUS
        elif redeem_deduct > 0:
            log_entry.consume_source = TokenConsumeSource.REDEEM
        elif log_entry.permanentDeduct > 0:
            log_entry.consume_source = TokenConsumeSource.PERMANENT
        else:
            # 兜底：如果产生 0 token 消耗或异常
            log_entry.consume_source = TokenConsumeSource.FREE

        # 4. 提交数据库
        # 记得更新 account 表的相关余额
        await self.db.commit()

    async def consume_tokens(
            self,
            account,
            actual_amount,
            user_id,
            request_id,
            free_amount: int = 0,
            monthly_amount: int = 0,
            bonus_amount: int = 0,
            redeem_amount: int = 0,
            permanent_amount: int = 0,
    ):
        # 新增额外流水
        await UserDAO.create_log(
            db=self.db,
            user_id=user_id,
            request_id=request_id,
            free_amount=free_amount,
            monthly_amount=monthly_amount,
            bonus_amount=bonus_amount,
            redeem_amount=redeem_amount,
            permanent_amount=permanent_amount,
            total_amount=actual_amount,
            balance_snapshot={
                "free": account.free_balance,
                "monthly": account.monthly_balance,
                "bonus": account.bonus_balance,
                "redeem": account.redeem_balance,
                "permanent": account.permanent_balance
            }
        )

        logger.info(
            f"[扣费] 成功 user_id={user_id}, free={free_amount}, bonus={bonus_amount}, redeem={redeem_amount}, monthly={monthly_amount}, permanent={permanent_amount}"
        )
