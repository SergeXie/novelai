import asyncio

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from common.config.get_db import get_db
from common.response.response_util import ResponseUtil
from core.deps.auth import get_login_user
from core.entity.do.generate_log import AiNovelGenerateLog
from dao.book_dao import BookDAO
from schemas import GenerateRequest, RefineRequest
from service.ai_service import get_today_input_output, get_total_input_output, get_today_used_chars, \
    calc_request_input_size, calc_request_input_length
from services import generate_novel_text, refine_novel_text, build_system_prompt
from fastapi.concurrency import run_in_threadpool

AI = APIRouter()

DAILY_TOTAL_CHAR_LIMIT = 2000000


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

    # todayTotalChars：你今天已经用掉的总字符数
    # todayLimit：你今天最多可以用的字符数
    # todayRemainingChars：你今天还剩多少字符可以用
    # totalUsedChars 累计用量
    # todayInputChars 今天用户输入的总字符数
    # todayOutputChars  今天系统生成输出的总字符数
    # todayTotalChars 今天输入 + 输出的字符总量
    # todayLimit 每日字符使用上限
    # todayRemainingChars 今天剩余可用字符数
    # totalInputChars  账号至今累计输入的字符总数
    # totalOutputChars 账号至今累计生成输出的字符总数
    # totalUsedChars 账号至今累计消耗的总字符数

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
    user=Depends(get_login_user),

):
    """
    根据设定生成小说片段（输入 / 输出全量留痕）
    """

    nodes_contents = await BookDAO.get_book_nodes_list(db, request.correlation, user.pkId)

    if not request.user_prompt:
        raise HTTPException(status_code=400, detail="提示词不能为空")

    # ========= 1️⃣ 限额校验 =========
    todayUsed = await get_today_used_chars(db, user.pkId)

    # 1️⃣ 调用模型生成
    content, final_prompt = await asyncio.to_thread(generate_novel_text, request, nodes_contents)
    try:
        if todayUsed + len(final_prompt) >= DAILY_TOTAL_CHAR_LIMIT:
            raise HTTPException(status_code=400, detail="今日生成额度已用完")

        outputLength = len(content)

        # 二次校验（防止超量）
        if todayUsed + len(final_prompt) + outputLength > DAILY_TOTAL_CHAR_LIMIT:
            raise HTTPException(status_code=400, detail="本次生成将超出今日额度")

        # 2️⃣ 成功流水
        log = AiNovelGenerateLog(
            userId=user.pkId,

            # ===== 输入 =====
            userPrompt=final_prompt,
            systemPrompt=None,
            requestInputLength=len(final_prompt),
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
        result = {"content": content, "len": len(content)}
        return ResponseUtil.success(data=result)


    except Exception as e:
        await db.rollback()

        # 3️⃣ 失败流水（输入也要记）
        failLog = AiNovelGenerateLog(
            userId=user.pkId,

            # ===== 输入 =====
            userPrompt=final_prompt,
            systemPrompt=None,
            requestInputLength=len(final_prompt),
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
async def refine_chapter(request: RefineRequest, db=Depends(get_db), user=Depends(get_login_user)):
    if not request.original_content or not request.suggestion:
        raise HTTPException(status_code=400, detail="原始内容和修改建议不能为空")

    requestInputLength, requestInput = calc_request_input_length(request)
    originalLen = len(request.original_content)
    suggestionLen = len(request.suggestion)
    try:
        content = refine_novel_text(request)

        print("content:{}".format(content))
        log = AiNovelGenerateLog(
            userId=user.pkId,
            actionType="refine",

            # ===== 结构化请求输入 =====
            requestInputLength=requestInputLength,

            # ===== 用户语义输入 =====
            userPrompt=requestInput,
            refineOriginalLength=originalLen,
            refineSuggestionLength=suggestionLen,
            model="doubao-seed-1-6-lite-251015",
            temperature=0.7,
            maxTokens=request.max_tokens,

            outputContent=content,
            outputLength=len(content),
            status=1
        )
        db.add(log)
        await db.commit()

        return {"content": content}
    except Exception as e:
        await db.rollback()

        # 3️⃣ 失败流水（输入也要记）
        failLog = AiNovelGenerateLog(
            userId=user.pkId,
            actionType="refine",

            # ===== 结构化请求输入 =====
            requestInputLength=requestInputLength,

            # ===== 用户语义输入 =====
            userPrompt=requestInput,
            refineOriginalLength=originalLen,
            refineSuggestionLength=suggestionLen,
            model="doubao-seed-1-6-lite-251015",
            temperature=0.7,
            maxTokens=request.max_tokens,

            outputContent=None,
            outputLength=0,
            status=0
        )
        db.add(failLog)
        await db.commit()
        raise HTTPException(status_code=500, detail="生成失败")



