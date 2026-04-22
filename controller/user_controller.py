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
from service.usage_service import UsageService
from service.user_service import UserService

userController = APIRouter()


@userController.get("/files/{filename}", name="返回媒体文件")
async def get_file(filename: str):
    file_path = os.path.join(settings.UPLOAD_USERS_DIR, filename)
    return FileResponse(file_path)


# @userController.post("/getUserFile", name="转发服务接收用户头像")
# async def user_upload(data: dict, db: AsyncSession = Depends(get_db)):
    # logger.info("转发服务接收用户头像..")
    # file_url = data.get("file_url")
    # user_id = data.get("user_id")
    #
    # if not file_url or not user_id:
    #     return {"code": 400, "msg": "参数缺失"}
    #
    # # 拼公网地址（如果传的是相对路径）
    # if file_url.startswith("/"):
    #     file_url = settings.CLOUD_ADDRESS.rstrip("/") + file_url
    #
    # try:
    #     # 1️⃣ 查询用户
    #     result = await db.execute(
    #         select(User).where(User.pkId == user_id)
    #     )
    #     user = result.scalar_one_or_none()
    #
    #     if not user:
    #         return {"code": 404, "msg": "用户不存在"}
    #
    #     # 2️⃣ 下载文件
    #     resp = requests.get(file_url, stream=True, timeout=300)
    #     if resp.status_code != 200:
    #         return {"code": 500, "msg": "下载失败"}
    #
    #     # 3️⃣ 生成文件名（保留后缀）
    #     # 从 URL 提取文件名
    #     path = urlparse(file_url).path
    #     original_name = os.path.basename(path)
    #
    #     file_path = os.path.join(settings.UPLOAD_USERS_DIR, original_name)
    #
    #     # 4️⃣ 保存文件
    #     with open(file_path, "wb") as f:
    #         for chunk in resp.iter_content(1024 * 1024):
    #             f.write(chunk)
    #
    #     # 5️⃣ 删除旧头像（可选但推荐）
    #     if user.avatar:
    #         old_path = os.path.join(settings.UPLOAD_USERS_DIR, os.path.basename(user.avatar))
    #         if os.path.exists(old_path):
    #             try:
    #                 os.remove(old_path)
    #             except:
    #                 pass
    #
    #     # 6️⃣ 生成访问 URL（不要存本地路径）
    #     avatar_url = f"{settings.CLOUD_ADDRESS}/files/{original_name}"
    #
    #     # 7️⃣ 更新数据库
    #     user.avatar = avatar_url
    #     await db.commit()
    #
    #     logger.info("头像更新成功 user_id={}".format(user_id))
    #
    #     return {
    #         "code": 0,
    #         "msg": "OK",
    #         "data": {
    #             "avatar": 0
    #         }
    #     }
    #
    #
    #
    # except Exception as e:
    #     return {"code": 500, "msg": str(e)}


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
    m = settings.MULTIPLIER
    usage_service = UsageService(db)

    # ===== 当天 =====
    todayInputChars, todayOutputChars = await usage_service.get_user_daily_input_output(user.pkId)
    todayInputChars, todayOutputChars = float(todayInputChars) * m, float(todayInputChars) * m

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

    user_daily_token_limit = settings.USER_DAILY_TOKEN_LIMIT

    data = {
        # ===== 用户信息 =====
        "userId": user.pkId,
        "account": user.account,
        "nickname": user.nickname,
        "avatar": user.avatar,
        # ===== 当天用量 =====
        "todayInputChars": todayInputChars,
        "todayOutputChars": todayOutputChars,
        "todayTotalChars": todayTotalChars,
        "todayLimit": user_daily_token_limit,
        "todayRemainingChars": max(
            user_daily_token_limit - todayTotalChars, 0
        ),
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