from datetime import datetime, time

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from ai.adapters.enums import AIAction, AIGenerateStatus
from common.config.config import settings
from common.exception.lzsd_exception import ServiceWarning, ServiceWarningSpecial
from core.entity.do.generate_log import AiNovelGenerateLog
from core.entity.do.users_do import User
from core.entity.vo.ai_response import AICompletionResponse, AIUserAssets
from core.enums.token_consume_source import TokenConsumeSource
from dao.ai_log_dao import AILogDAO
from dao.ai_model_dao import AiModelDAO
from dao.user_account_dao import UserAccountDAO
from service.account_service import AccountService


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

    async def get_user_daily_input_output(self, user_id: int) -> tuple[int, int]:
        """获取用户今天累计的输入长度和输出长度。"""
        start, end = self.get_today_range()
        intput_count, output_count, _, _, _ = await self.ai_log_dao.get_usage_sum(user_id, start, end)
        return intput_count, output_count

    async def get_user_total_input_output(self, user_id: int) -> tuple[int, int]:
        """获取用户历史累计的输入长度和输出长度。"""
        intput_total_count, output_total_count, actualAmount, freeDeduct, permanentDeduct = await self.ai_log_dao.get_usage_sum(user_id)
        return intput_total_count, output_total_count

    async def check_quota_or_raise(self,
                                   frozen_token_length: int,
                                   user_info: User):

        user_id = user_info.pkId

        is_free_user = True

        user_account = await AccountService.get_account_info(db=self.db, user_id=user_id)
        if user_account and user_account.total_amount > frozen_token_length:
            is_free_user = False

        if is_free_user:
            # 免费用户受平台维度限制，避免当天总消耗超过平台配置上限。
            start, end = self.get_today_range()
            platform_total = await self.ai_log_dao.get_platform_usage_sum(start, end)
            if platform_total + frozen_token_length > settings.PLATFORM_DAILY_TOKEN_LIMIT:
                logger.error("平台今日总额度已耗尽")
                raise ServiceWarning(message="服务器繁忙，请明天再试")

            # 3. 用户维度限制。
            #    这里会把今天输入+输出的累计值，再加上本次请求长度后乘倍率进行判断。
            input_daily_total, output_daily_total = await self.get_user_daily_input_output(user_id)
            total = input_daily_total + output_daily_total
            limit = settings.USER_DAILY_TOKEN_LIMIT
            usage = float(total + frozen_token_length) * settings.MULTIPLIER

            logger.info(f"倍率:{settings.MULTIPLIER} 限额:{limit} 已用:{usage} 用户id:{user_id}")

            if usage > limit:
                logger.error(f"用户id:{user_id} 今日总额度已耗尽")
                raise ServiceWarningSpecial(message="您今日的生成额度已用完")

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
            totalTokens:int = 0,
            actualAmount:int = 0,
            consumeSource:TokenConsumeSource = TokenConsumeSource.FREE,
            freeDeduct:int = 0,
            monthlyDeduct:int = 0,
            permanentDeduct:int = 0
    ):
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
            requestInputLength=len(user_prompt),
            model=model_name,
            temperature=temperature,
            maxTokens=max_tokens,
            # 输出信息
            outputContent=output_content,
            outputLength=len(output_content),
            # 这里只是粗略估算，不是严格 tokenizer 结果。
            tokenEstimate=len(output_content) // 2,
            actionType=action_type.value,
            status=status.value
        )
        await self.ai_log_dao.create_ai_generate_log(log_obj=log)

    async def poll_content_by_request_id(self, request_id: str, user_id:int):
        """根据 request_id 查询生成内容，常用于前端轮询结果。"""
        log_record = await self.ai_log_dao.get_log_by_request_id(request_id=request_id, user_id=user_id)

        if log_record:
            return log_record.outputContent

        return None

    async def update_output_content_by_request_id(
            self,
            request_id: str,
            ai_rsp: AICompletionResponse
    ):
        """根据 request_id 更新生成后的输出内容。"""
        if not request_id:
            return False

        success = await self.ai_log_dao.update_output_by_request_id(
            request_id=request_id,
            content=ai_rsp.content,
        )

        if success:
            logger.info(f"RequestId: {request_id} 内容更新成功")
        else:
            logger.error(f"RequestId: {request_id} 内容更新失败")

        return success

    async def get_book_chat_history(self, bid: str, page: int, size: int):
        """分页获取某本书下的 AI 对话历史。"""
        logs, total = await self.ai_log_dao.get_logs_by_bid_paged(bid, page, size)

        # 组装成前端更容易消费的返回结构。
        list_data = []
        for log in logs:
            list_data.append({
                "requestId": log["requestId"],
                # 列表页只截取前 200 个字符作为预览，避免内容过长。
                "prompt": log["originPrompt"][:200] + ("..." if len(log["originPrompt"]) > 200 else ""),
                "status": log["status"],  # 1: 成功, 0: 失败, 2: 进行中
                "action": log["actionType"],  # generate / refine
                "createdAt": log["createdAt"].strftime("%Y-%m-%d %H:%M:%S")
            })

        return {
            "list": list_data,
            "total": total,
            "page": page,
            "size": size
        }

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