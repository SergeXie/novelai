import os
import uuid
from urllib.parse import urlparse
import requests
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import select
from starlette.responses import FileResponse
from loguru import logger
from common.config.config import settings
from common.config.get_db import get_db
from common.response.response_util import ResponseUtil
from core.deps.auth import get_current_user, check_user_quota_or_raise
from core.entity.do.users_do import User
from core.entity.vo.user_vo import UpdateNicknameRequest
from dao.user_dao import UserDAO
from service.account_service import AccountService
from service.usage_service import UsageService
from service.user_service import UserService

userController = APIRouter()



@userController.post("/updateNickname", name="修改昵称")
async def update_nickname(
    req: UpdateNicknameRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    修改昵称
    """

    await UserService.update_nickname(
        db=db,
        user_id=user.pkId,
        nickname=req.nickname
    )

    await db.commit()

    return ResponseUtil.success(msg="修改成功")

@userController.get("/userInfo", name="用户信息")
async def user_info(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    await AccountService.claim_due_bonus_plans(db, user.pkId)

    m = settings.MULTIPLIER
    usage_service = UsageService(db)

    # ===== 当天 =====
    todayInputChars, todayOutputChars = await usage_service.get_user_monthly_input_output(user.pkId)
    todayInputChars, todayOutputChars = float(todayInputChars) * m, float(todayOutputChars) * m
    monthFreeUsed = await usage_service.get_user_monthly_free_used(user.pkId)

    # ===== 累计 =====
    totalInputChars, totalOutputChars = await usage_service.get_user_total_input_output(user.pkId)
    totalInputChars, totalOutputChars = float(totalInputChars) * m, float(totalOutputChars) * m

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

    user_daily_token_limit = settings.USER_MONTHLY_FREE_TOKEN_LIMIT

    query_user = await UserDAO.get_by_uuid(db, user_uuid=user.uuid)

    data = {
        # ===== 用户信息 =====
        "isBindWechat": query_user.isBindWechat if query_user else 0,
        "userId": user.pkId,
        "account": user.account,
        "nickname": query_user.nickname if query_user else user.nickname,
        "avatar": query_user.avatar if query_user else user.avatar,
        # ===== 当天用量 =====
        "todayInputChars": todayInputChars,
        "todayOutputChars": todayOutputChars,
        "todayTotalChars": todayTotalChars,
        "todayLimit": user_daily_token_limit,
        "todayRemainingChars": max(
            user_daily_token_limit - monthFreeUsed, 0
        ),
        "monthInputChars": todayInputChars,
        "monthOutputChars": todayOutputChars,
        "monthTotalChars": todayTotalChars,
        "monthFreeUsed": monthFreeUsed,
        "monthLimit": user_daily_token_limit,
        "monthRemainingChars": max(user_daily_token_limit - monthFreeUsed, 0),
        # ===== 累计用量 =====
        "totalInputChars": totalInputChars,
        "totalOutputChars": totalOutputChars,
        "totalUsedChars": totalInputChars + totalOutputChars
    }

    return ResponseUtil.success(data=data)

@userController.get("/checkQuote", name="检测token是否超标")
async def user_quote_check(
    frozen: int = Query(5000, description="预冻结/需检查的额度"), # 增加 frozen 参数
    user=Depends(get_current_user),
):
    await check_user_quota_or_raise(frozen_token_length=frozen, user_info=user)

    return ResponseUtil.success(data=frozen)
