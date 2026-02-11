from fastapi import APIRouter, HTTPException, Depends
from common.config.get_db import get_db
from core.deps.auth import get_login_user
from core.entity.do.generate_log import AiNovelGenerateLog
from schemas import GenerateRequest, RefineRequest
from services import generate_novel_text, refine_novel_text, build_system_prompt

AI = APIRouter()


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

@AI.post("/generate", summary="根据设定生成小说片段")
async def generate_chapter(
    request: GenerateRequest,
    db=Depends(get_db),
    user=Depends(get_login_user)
):
    """
    根据设定生成小说片段（输入 / 输出全量留痕）
    """
    print("request:{}".format(request))
    if not request.user_prompt:
        raise HTTPException(status_code=400, detail="提示词不能为空")

    systemPrompt = build_system_prompt(request)

    try:
        # 1️⃣ 调用模型生成
        content = generate_novel_text(request)

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
        print("len:{}".format(len(content)))
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
async def refine_chapter(request: RefineRequest):
    if not request.original_content or not request.suggestion:
        raise HTTPException(status_code=400, detail="原始内容和修改建议不能为空")

    content = refine_novel_text(request)
    print("content:{}".format(content))
    return {"content": content}