from fastapi import APIRouter, BackgroundTasks, Body, Depends

from ai.adapters.enums import AIProvider
from common.config.get_db import get_db
from common.response.response_util import ResponseUtil
from core.deps.auth import get_current_user
from core.entity.do.users_do import User
from service.ai_service import AIService

aiImageController = APIRouter(prefix="/ai/image", tags=["AI文生图"])


async def _generate_image(
    background_tasks: BackgroundTasks,
    level: int,
    size: str,
    prompt: str,
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not prompt or not prompt.strip():
        return ResponseUtil.failure(msg="提示词不能为空")
    if not size or not size.strip():
        return ResponseUtil.failure(msg="图片尺寸不能为空")

    ai_srv = AIService(db=db)

    try:
        request_id, _ = await ai_srv.generate_image(
            user=current_user,
            prompt=prompt.strip(),
            provider=AIProvider.parse(level),
            size=size.strip(),
            n=1,
            watermark=False,
            background_tasks=background_tasks,
        )
    except ValueError as exc:
        return ResponseUtil.failure(msg=str(exc))
    except Exception as exc:
        return ResponseUtil.error(msg=str(exc))

    return ResponseUtil.success(data={"requestId": request_id})


@aiImageController.post("/generate", summary="文生图")
async def generate_image(
    background_tasks: BackgroundTasks,
    level: int = Body(10, embed=True, description="模型等级/供应商"),
    size: str = Body("2K", embed=True, description="图片尺寸，如 1024x1024、2K、4K"),
    prompt: str = Body(..., description="图片生成提示词"),
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _generate_image(
        background_tasks=background_tasks,
        level=level,
        size=size,
        prompt=prompt,
        db=db,
        current_user=current_user,
    )


@aiImageController.post("/generate/avatar", summary="生成头像")
async def generate_avatar(
    background_tasks: BackgroundTasks,
    level: int = Body(10, embed=True, description="模型等级/供应商"),
    prompt: str = Body(None, description="图片生成提示词，为空时使用默认"),
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    DEFAULT_AVATAR_PROMPT = "一个可爱的头像"
    # 如果 prompt 为空，使用默认提示词
    if not prompt or not prompt.strip():
        prompt = DEFAULT_AVATAR_PROMPT
    return await _generate_image(
        background_tasks=background_tasks,
        level=level,
        size="1024x1024",
        prompt=prompt,
        db=db,
        current_user=current_user,
    )


@aiImageController.post("/generate/cover", summary="生成封面")
async def generate_cover(
    background_tasks: BackgroundTasks,
    level: int = Body(10, embed=True, description="模型等级/供应商"),
    prompt: str = Body(None, description="图片生成提示词，为空时使用默认"),
    book_name: str = Body("", description="书名，用于生成默认提示词"),
    summary: str = Body("", description="简介，用于生成默认提示词"),
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    DEFAULT_COVER_PROMPT = "一本科幻小说的封面"
    # 如果 prompt 为空，使用默认提示词
    if not prompt or not prompt.strip():
        prompt = DEFAULT_COVER_PROMPT
    # 有书名或简介时，直接在提示词后拼接
    if book_name:
        prompt = f"{prompt}，书名《{book_name}》"
    if summary:
        prompt = f"{prompt}，{summary}"
    return await _generate_image(
        background_tasks=background_tasks,
        level=level,
        size="800x1200",
        prompt=prompt,
        db=db,
        current_user=current_user,
    )