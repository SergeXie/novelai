from datetime import datetime, time

from fastapi import HTTPException
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from common.config.config import settings
from common.exception.lzsd_exception import ServiceWarning, ServiceWarningSpecial
from core.entity.do.generate_log import AiNovelGenerateLog
from dao.ai_log_dao import AILogDAO
from dao.ai_model_dao import AiModelDAO


def get_today_range():
    """返回今天 00:00:00 到 23:59:59.999999 的时间范围。"""
    today = datetime.now().date()
    return (
        datetime.combine(today, time.min),
        datetime.combine(today, time.max)
    )


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

    @staticmethod
    def get_today_range():
        """类内同名工具方法，作用和模块级 get_today_range 一样。"""
        today = datetime.now().date()
        start = datetime.combine(today, time.min)
        end = datetime.combine(today, time.max)
        return start, end

    async def get_user_daily_input_output(self, user_id: int) -> tuple[int, int]:
        """获取用户今天累计的输入长度和输出长度。"""
        start, end = get_today_range()
        intput_count, output_count = await self.ai_log_dao.get_usage_sum(user_id, start, end)
        return intput_count, output_count

    async def get_user_total_input_output(self, user_id: int) -> tuple[int, int]:
        """获取用户历史累计的输入长度和输出长度。"""
        intput_total_count, output_total_count = await self.ai_log_dao.get_usage_sum(user_id)
        return intput_total_count, output_total_count

    async def check_quota_or_raise(self, user_id: int, current_request_len: int):
        """做三层额度校验：单次请求、平台日额度、用户日额度。"""
        # 1. 单次请求不能超过系统允许的最大长度。
        if current_request_len > settings.SINGLE_REQUEST_TOKEN_LIMIT:
            raise ServiceWarning(message="请求内容过长，请分段发送")

        start, end = get_today_range()

        # 2. 平台维度限制，避免当天总消耗超过平台配置上限。
        platform_total = await self.ai_log_dao.get_platform_usage_sum(start, end)
        if platform_total + current_request_len > settings.PLATFORM_DAILY_TOKEN_LIMIT:
            logger.error("平台今日总额度已耗尽")
            raise ServiceWarning(message="服务器繁忙，请明天再试")

        # 3. 用户维度限制。
        #    这里会把今天输入+输出的累计值，再加上本次请求长度后乘倍率进行判断。
        input_daily_total, output_daily_total = await self.get_user_daily_input_output(user_id)
        total = input_daily_total + output_daily_total
        limit = settings.USER_DAILY_TOKEN_LIMIT
        usage = float(total + current_request_len) * settings.MULTIPLIER

        logger.info(f"倍率:{settings.MULTIPLIER} 限额:{limit} 已用:{usage} 用户id:{user_id}")

        if usage > limit:
            logger.error(f"用户id:{user_id} 今日总额度已耗尽")
            raise ServiceWarningSpecial(message="您今日的生成额度已用完")

    async def record(
            self,
            user_id: int,
            level: int,
            bid: str,
            node_ids,
            origin_prompt: str,
            request_id: str,
            system_prompt: str,
            user_prompt: str,
            temperature: float,
            output_content: str,
            action_type: str
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
            actionType=action_type,
            # 状态：这里固定写 1，表示本次生成记录成功。
            status=1
        )
        await self.ai_log_dao.create_ai_generate_log(log_obj=log)

    async def poll_content_by_request_id(self, request_id: str):
        """根据 request_id 查询生成内容，常用于前端轮询结果。"""
        log_record = await self.ai_log_dao.get_log_by_request_id(request_id=request_id)

        if log_record:
            return log_record.outputContent

        return None

    async def update_output_content_by_request_id(
            self,
            request_id: str,
            content: str
    ):
        """根据 request_id 更新生成后的输出内容。"""
        if not request_id:
            return False

        success = await self.ai_log_dao.update_output_by_request_id(
            request_id=request_id,
            content=content,
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
