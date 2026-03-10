from datetime import datetime, time

from fastapi import HTTPException
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from common.config.config import settings
from core.entity.do.generate_log import AiNovelGenerateLog
from dao.ai_log_dao import AILogDAO
from dao.ai_model_dao import AiModelDAO


def get_today_range():
    today = datetime.now().date()
    return (
        datetime.combine(today, time.min),
        datetime.combine(today, time.max)
    )

class UsageService:

    def __init__(self, db: AsyncSession):
        self.ai_log_dao = AILogDAO(db)
        self.model_dao = AiModelDAO(db)

    @staticmethod
    def get_today_range():
        today = datetime.now().date()
        start = datetime.combine(today, time.min)
        end = datetime.combine(today, time.max)
        return start, end


    async def get_user_daily_input_output(self, user_id: int) -> tuple[int, int]:
        start, end = get_today_range()
        intput_count, output_count = await self.ai_log_dao.get_usage_sum(user_id, start, end)
        return intput_count, output_count

    async def get_user_total_input_output(self, user_id: int) -> tuple[int, int]:
        intput_total_count, output_total_count = await self.ai_log_dao.get_usage_sum(user_id)
        return intput_total_count, output_total_count

    async def check_quota_or_raise(self, user_id: int, current_request_len: int):
        """
        三层限额校验：单次、个人每日、平台每日
        """
        # 1. 校验单次请求是否过大
        if current_request_len > settings.SINGLE_REQUEST_TOKEN_LIMIT:
            raise HTTPException(status_code=400, detail="请求内容过长，请分段发送")

        start, end = get_today_range()

        # 2. 校验全平台总额度
        platform_total = await self.ai_log_dao.get_platform_usage_sum(start, end)
        if platform_total + current_request_len > settings.PLATFORM_DAILY_TOKEN_LIMIT:
            logger.error("平台今日总额度已耗尽！")
            raise HTTPException(status_code=503, detail="服务器繁忙，请明天再试")

        # 3. 校验个人每日额度
        input_daily_total, output_daily_total = await self.get_user_daily_input_output(user_id)
        total = input_daily_total + output_daily_total
        limit = settings.USER_DAILY_TOKEN_LIMIT
        usage = float((total + current_request_len)) * settings.MULTIPLIER

        logger.info(f"倍率:{settings.MULTIPLIER}  限额:{limit}  已用:{usage} 用户id：{user_id}")

        if usage > limit:
            logger.error(f"用户id:{user_id} 今日总额度已耗尽！")
            raise HTTPException(status_code=429, detail="您今日的生成额度已用完")

    async def record(self, user_id: int,
                     level: int,
                     bid:str,
                     node_ids,
                     origin_prompt:str,
                     request_id:str,
                     system_prompt:str,
                     user_prompt: str,
                     temperature:float,
                     output_content:str,
                     action_type:str):
        # 查 models
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
            # ===== 输入 =====
            userPrompt=user_prompt,
            systemPrompt=system_prompt,
            requestInputLength=len(user_prompt) * ai_model_multiplier,
            model=model_name,
            temperature=temperature,
            maxTokens=max_tokens,
            # ===== 输出 =====
            outputContent=output_content,
            outputLength=len(output_content)* ai_model_multiplier,
            tokenEstimate=len(output_content) // 2,
            actionType=action_type,
            # ===== 状态 =====
            status=1
        )
        await self.ai_log_dao.create_ai_generate_log(log_obj=log)

    async def poll_content_by_request_id(self, request_id: str):
        """
        根据 request_id 获取生成内容，并进行业务状态判定
        """
        # 1. 调用 DAO 获取记录
        log_record = await self.ai_log_dao.get_log_by_request_id(request_id=request_id)

        if log_record:
            return log_record.outputContent

        return None

    async def update_output_content_by_request_id(
            self,
            request_id: str,
            content: str
    ):
        """
        异步更新 AI 生成结果及相关元数据
        """
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
        # 调用 DAO
        logs, total = await self.ai_log_dao.get_logs_by_bid_paged(bid, page, size)

        # 组装返回数据
        list_data = []
        for log in logs:
            list_data.append({
                "requestId": log["requestId"],
                # 列表页只显示前 100 个字符预览，节省网络带宽和前端渲染压力
                "prompt": log["originPrompt"][:200] + ("..." if len(log["originPrompt"]) > 200 else ""),
                "status": log["status"],  # 1:成功, 0:失败, 2:进行中
                "action": log["actionType"],  # generate / refine
                "createdAt": log["createdAt"].strftime("%Y-%m-%d %H:%M:%S")
            })

        return {
            "list": list_data,
            "total": total,
            "page": page,
            "size": size
        }


