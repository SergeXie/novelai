import json
from datetime import datetime, time
from fastapi import HTTPException
from loguru import logger
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from common.config.config import settings
from core.entity.do.generate_log import AiNovelGenerateLog
from dao.ai_log_dao import AILogDAO
from dao.ai_model_dao import AiModelDAO
from schemas import GenerateRequest


def get_today_range():
    today = datetime.now().date()
    return (
        datetime.combine(today, time.min),
        datetime.combine(today, time.max)
    )


class UsageService:

    def __init__(self, db: AsyncSession):
        self.dao = AILogDAO(db)

    def get_today_range(self):
        today = datetime.now().date()
        start = datetime.combine(today, time.min)
        end = datetime.combine(today, time.max)
        return start, end

    async def get_today_used_chars(
            self,
            db: AsyncSession,
            user_id: int
    ) -> int:
        start, end = get_today_range()

        stmt = select(
            func.coalesce(
                func.sum(
                    AiNovelGenerateLog.requestInputLength
                    + AiNovelGenerateLog.outputLength
                ),
                0
            )
        ).where(
            AiNovelGenerateLog.userId == user_id,
            AiNovelGenerateLog.createdAt >= start,
            AiNovelGenerateLog.createdAt <= end,
            AiNovelGenerateLog.status == 1
        )

        result = await db.execute(stmt)
        return result.scalar_one()

    async def get_today_input_output(
            self,
            db: AsyncSession,
            user_id: int
    ) -> tuple[int, int]:
        start, end = get_today_range()

        stmt = select(
            func.coalesce(func.sum(AiNovelGenerateLog.requestInputLength), 0),
            func.coalesce(func.sum(AiNovelGenerateLog.outputLength), 0)
        ).where(
            AiNovelGenerateLog.userId == user_id,
            AiNovelGenerateLog.status == 1,
            AiNovelGenerateLog.createdAt >= start,
            AiNovelGenerateLog.createdAt <= end
        )

        result = await db.execute(stmt)
        input_chars, output_chars = result.one()
        return input_chars, output_chars

    async def get_total_input_output(
            self,
            db: AsyncSession,
            user_id: int
    ) -> tuple[int, int]:
        stmt = select(
            func.coalesce(func.sum(AiNovelGenerateLog.requestInputLength), 0),
            func.coalesce(func.sum(AiNovelGenerateLog.outputLength), 0)
        ).where(
            AiNovelGenerateLog.userId == user_id,
            AiNovelGenerateLog.status == 1
        )

        result = await db.execute(stmt)
        input_chars, output_chars = result.one()
        return input_chars, output_chars

    def calc_request_input_size(self, req: GenerateRequest) -> int:
        """
        统计整个生成请求的输入字符数
        """
        data = req.model_dump()  # Pydantic v2
        json_str = json.dumps(data, ensure_ascii=False)
        print(json_str)
        print("len:{}".format(len(json_str)))
        return len(json_str), json_str

    import json

    def calc_request_input_length(self, request) -> int:
        """
        统计整个请求对象（JSON）的字符数
        """
        data = request.model_dump()  # Pydantic v2
        json_str = json.dumps(data, ensure_ascii=False)
        return len(json_str), json_str

    async def get_today_usage(self, user_id: int) -> dict:
        """获取今日消耗"""
        start, end = get_today_range()
        input_sum, output_sum = await self.dao.get_usage_sum(user_id, start, end)
        return {
            "input": input_sum,
            "output": output_sum,
            "total": input_sum + output_sum
        }

    async def get_total_usage(self, user_id: int) -> dict:
        """获取历史总消耗"""
        # 不传时间即为全表统计
        input_sum, output_sum = await self.dao.get_usage_sum(user_id)
        return {
            "input": input_sum,
            "output": output_sum,
            "total": input_sum + output_sum
        }

    async def check_quota_or_raise(self, user_id: int, current_request_len: int):
        """
        三层限额校验：单次、个人每日、平台每日
        """
        # 1. 校验单次请求是否过大
        if current_request_len > settings.SINGLE_REQUEST_TOKEN_LIMIT:
            raise HTTPException(status_code=400, detail="请求内容过长，请分段发送")

        start, end = get_today_range()

        # 2. 校验全平台总额度
        platform_total = await self.dao.get_platform_usage_sum(start, end)
        if platform_total + current_request_len > settings.PLATFORM_DAILY_TOKEN_LIMIT:
            logger.error("平台今日总额度已耗尽！")
            raise HTTPException(status_code=503, detail="服务器繁忙，请明天再试")

        # 3. 校验个人每日额度
        user_stats = await self.get_today_usage(user_id)
        print(user_stats["total"] + current_request_len)
        limit = settings.USER_DAILY_TOKEN_LIMIT
        usage = float((user_stats["total"] + current_request_len)) * settings.MULTIPLIER

        logger.error(f"倍率:{settings.MULTIPLIER}  限额:{limit}  已用:{usage} 用户id：{user_id}")

        if usage > limit:
            logger.error(f"用户id:{user_id} 今日总额度已耗尽！")
            raise HTTPException(status_code=429, detail="您今日的生成额度已用完")

    async def record(self,db: AsyncSession,user_id: int,
                     level: int,
                     system_prompt:str,
                     user_prompt: str,
                     model_name:str,
                     temperature:float,
                     max_tokens:int,
                     output_content:str):
        # 查 models
        ai_model_multiplier = await AiModelDAO.first_ai_models(db, level)

        log = AiNovelGenerateLog(
            userId=user_id,
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

            # ===== 状态 =====
            status=1
        )

        await self.dao.create_ai_generate_log(log_obj=log)


