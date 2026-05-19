from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from common.config.config import settings
from common.config.get_db import get_db
from common.response.response_util import ResponseUtil
from core.deps.auth import check_user_quota_or_raise, get_current_user
from core.entity.vo.user_vo import UpdateAvatarRequest, UpdateNicknameRequest
from dao.user_dao import UserDAO
from service.account_service import AccountService
from service.usage_service import UsageService
from service.user_service import UserService

userController = APIRouter()


@userController.post("/updateNickname", name="update nickname")
async def update_nickname(
    req: UpdateNicknameRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    await UserService.update_nickname(
        db=db,
        user_id=user.pkId,
        nickname=req.nickname,
    )

    await db.commit()

    return ResponseUtil.success(msg="success")


@userController.post("/updateAvatar", name="update avatar")
async def update_avatar(
    req: UpdateAvatarRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    if int(user.pkId) != req.userId:
        return ResponseUtil.failure(msg="cannot update another user avatar")

    avatar_url = str(req.avatar_url)

    avatar_path = await UserService.update_avatar(
        db=db,
        userId=req.userId,
        avatar_url=avatar_url,
    )

    await db.commit()

    return ResponseUtil.success(
        data={
            "avatar": UserService.build_avatar_url(avatar_path),
            "avatarPath": avatar_path,
        },
        msg="success",
    )


@userController.get("/userInfo", name="user info")
async def user_info(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    await AccountService.claim_due_bonus_plans(db, user.pkId)

    multiplier = settings.MULTIPLIER
    usage_service = UsageService(db)

    month_input_chars, month_output_chars = await usage_service.get_user_monthly_input_output(user.pkId)
    month_input_chars = float(month_input_chars) * multiplier
    month_output_chars = float(month_output_chars) * multiplier
    month_total_chars = month_input_chars + month_output_chars
    month_free_used = await usage_service.get_user_monthly_free_used(user.pkId)

    total_input_chars, total_output_chars = await usage_service.get_user_total_input_output(user.pkId)
    total_input_chars = float(total_input_chars) * multiplier
    total_output_chars = float(total_output_chars) * multiplier

    monthly_free_limit = settings.USER_MONTHLY_FREE_TOKEN_LIMIT
    monthly_free_remaining = max(monthly_free_limit - month_free_used, 0)

    query_user = await UserDAO.get_by_uuid(db, user_uuid=user.uuid)

    data = {
        "isBindWechat": query_user.isBindWechat if query_user else 0,
        "userId": user.pkId,
        "account": user.account,
        "nickname": query_user.nickname if query_user else user.nickname,
        "avatar": UserService.build_avatar_url(query_user.avatar if query_user else user.avatar),
        # Backward compatibility: today* fields currently use monthly quota data.
        "todayInputChars": month_input_chars,
        "todayOutputChars": month_output_chars,
        "todayTotalChars": month_total_chars,
        "todayLimit": monthly_free_limit,
        "todayRemainingChars": monthly_free_remaining,
        "monthInputChars": month_input_chars,
        "monthOutputChars": month_output_chars,
        "monthTotalChars": month_total_chars,
        "monthFreeUsed": month_free_used,
        "monthLimit": monthly_free_limit,
        "monthRemainingChars": monthly_free_remaining,
        "totalInputChars": total_input_chars,
        "totalOutputChars": total_output_chars,
        "totalUsedChars": total_input_chars + total_output_chars,
    }

    return ResponseUtil.success(data=data)


@userController.get("/checkQuote", name="check quota")
async def user_quote_check(
    frozen: int = Query(5000, description="quota amount to check"),
    user=Depends(get_current_user),
):
    await check_user_quota_or_raise(frozen_token_length=frozen, user_info=user)

    return ResponseUtil.success(data=frozen)
