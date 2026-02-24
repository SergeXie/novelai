from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from common.config.get_db import get_db
from common.response.response_util import ResponseUtil
from core.deps.auth import get_login_user
from core.entity.do.generate_log import AiNovelGenerateLog
from schemas import GenerateRequest, RefineRequest
from services import generate_novel_text, refine_novel_text, build_system_prompt
from datetime import datetime, time

AI = APIRouter()

DAILY_TOTAL_CHAR_LIMIT = 2000000


# @AI.post("/generate", summary="根据设定生成小说片段")
# async def generate_chapter(request: GenerateRequest, user=Depends(get_login_user)):
#     """
#     接收人物、题材和提示词，返回生成的小说文本。
#     """
#     if not request.user_prompt:
#         raise HTTPException(status_code=400, detail="提示词不能为空")
#
#     content = generate_novel_text(request)
#     print(content)
#     return {"content": content}


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
                func.length(AiNovelGenerateLog.userPrompt)
                + func.length(AiNovelGenerateLog.outputContent)
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


async def get_today_total_chars(
    db: AsyncSession,
    user_id: int
) -> int:
    start, end = get_today_range()

    stmt = select(
        func.coalesce(
            func.sum(
                func.length(AiNovelGenerateLog.userPrompt)
                + func.length(AiNovelGenerateLog.outputContent)
            ),
            0
        )
    ).where(
        AiNovelGenerateLog.userId == user_id,
        AiNovelGenerateLog.status == 1,
        AiNovelGenerateLog.createdAt >= start,
        AiNovelGenerateLog.createdAt <= end
    )

    result = await db.execute(stmt)
    return result.scalar_one()

async def get_total_used_chars(
    db: AsyncSession,
    user_id: int
) -> int:
    stmt = select(
        func.coalesce(
            func.sum(
                func.length(AiNovelGenerateLog.userPrompt)
                + func.length(AiNovelGenerateLog.outputContent)
            ),
            0
        )
    ).where(
        AiNovelGenerateLog.userId == user_id,
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
        func.coalesce(func.sum(func.length(AiNovelGenerateLog.userPrompt)), 0),
        func.coalesce(func.sum(func.length(AiNovelGenerateLog.outputContent)), 0)
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
        func.coalesce(func.sum(func.length(AiNovelGenerateLog.userPrompt)), 0),
        func.coalesce(func.sum(func.length(AiNovelGenerateLog.outputContent)), 0)
    ).where(
        AiNovelGenerateLog.userId == user_id,
        AiNovelGenerateLog.status == 1
    )

    result = await db.execute(stmt)
    input_chars, output_chars = result.one()
    return input_chars, output_chars


@AI.get("/userInfo", name="用户信息")
async def user_info(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_login_user)
):
    # ===== 当天 =====
    todayInputChars, todayOutputChars = await get_today_input_output(
        db, user.pkId
    )

    # ===== 累计 =====
    totalInputChars, totalOutputChars = await get_total_input_output(
        db, user.pkId
    )

    todayTotalChars = todayInputChars + todayOutputChars

    data= {
        # ===== 用户信息 =====
        "userId": user.pkId,
        "uuid": user.uuid,
        "account": user.account,
        "nickname": user.nickname,

        # ===== 当天用量 =====
        "todayInputChars": todayInputChars,
        "todayOutputChars": todayOutputChars,
        "todayTotalChars": todayTotalChars,
        "todayLimit": DAILY_TOTAL_CHAR_LIMIT,
        "todayRemainingChars": max(
            DAILY_TOTAL_CHAR_LIMIT - todayTotalChars, 0
        ),

        # ===== 累计用量 =====
        "totalInputChars": totalInputChars,
        "totalOutputChars": totalOutputChars,
        "totalUsedChars": totalInputChars + totalOutputChars
    }

    return ResponseUtil.success(data=data)


@AI.post("/generate", summary="根据设定生成小说片段")
async def generate_chapter(
    request: GenerateRequest,
    db=Depends(get_db),
    user=Depends(get_login_user)
):
    """
    根据设定生成小说片段（输入 / 输出全量留痕）
    """
    if not request.user_prompt:
        raise HTTPException(status_code=400, detail="提示词不能为空")

    systemPrompt = build_system_prompt(request)

    # ========= 1️⃣ 限额校验 =========
    todayUsed = await get_today_used_chars(db, user.pkId)

    currentInputSize = (
            len(request.user_prompt) + len(systemPrompt)
    )

    if todayUsed + currentInputSize >= DAILY_TOTAL_CHAR_LIMIT:
        raise HTTPException(status_code=400, detail="今日生成额度已用完")

    try:
        # 1️⃣ 调用模型生成
        content = generate_novel_text(request)
        outputLength = len(content)

        # 二次校验（防止超量）
        if todayUsed + currentInputSize + outputLength > DAILY_TOTAL_CHAR_LIMIT:
            raise HTTPException(status_code=400, detail="本次生成将超出今日额度")

        # 2️⃣ 成功流水
        log = AiNovelGenerateLog(
            userId=user.pkId,

            # ===== 输入 =====
            userPrompt=request.user_prompt,
            systemPrompt=systemPrompt,
            model="doubao-seed-1-6-lite-251015",
            temperature=0.7,
            maxTokens=request.max_tokens,

            # ===== 输出 =====
            outputContent=content,
            outputLength=len(content),
            tokenEstimate=len(content) // 2,

            # ===== 状态 =====
            status=1
        )
        db.add(log)
        await db.commit()
        return {"content": content, "len": len(content)}

    except Exception as e:
        await db.rollback()

        # 3️⃣ 失败流水（输入也要记）
        failLog = AiNovelGenerateLog(
            userId=user.pkId,

            # ===== 输入 =====
            userPrompt=request.user_prompt,
            systemPrompt=systemPrompt,
            model="doubao-seed-1-6-lite-251015",
            temperature=0.7,
            maxTokens=request.max_tokens,

            # ===== 输出 =====
            outputContent=None,
            outputLength=0,
            tokenEstimate=0,

            # ===== 状态 =====
            status=0,
            errorMsg=str(e)
        )
        db.add(failLog)
        await db.commit()

        raise HTTPException(status_code=500, detail="生成失败")


@AI.post("/refine", summary="根据建议微调文本")
async def refine_chapter(request: RefineRequest, user=Depends(get_login_user)):
    if not request.original_content or not request.suggestion:
        raise HTTPException(status_code=400, detail="原始内容和修改建议不能为空")

    content = refine_novel_text(request)
    print("content:{}".format(content))
    return {"content": content}