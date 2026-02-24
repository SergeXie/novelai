import json
from datetime import datetime, time
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from core.entity.do.generate_log import AiNovelGenerateLog
from schemas import GenerateRequest


def get_today_range():
    today = datetime.now().date()
    start = datetime.combine(today, time.min)
    end = datetime.combine(today, time.max)
    return start, end


async def get_today_used_chars(
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



def calc_request_input_size(req: GenerateRequest) -> int:
    """
    统计整个生成请求的输入字符数
    """
    data = req.model_dump()  # Pydantic v2
    json_str = json.dumps(data, ensure_ascii=False)
    print(json_str)
    print("len:{}".format(len(json_str)))
    return len(json_str), json_str


import json

def calc_request_input_length(request) -> int:
    """
    统计整个请求对象（JSON）的字符数
    """
    data = request.model_dump()  # Pydantic v2
    json_str = json.dumps(data, ensure_ascii=False)
    return len(json_str), json_str