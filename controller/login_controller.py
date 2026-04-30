import json
import uuid
from datetime import timedelta, datetime
from typing import Optional
from urllib.parse import quote
import bcrypt
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from common.config.config import settings
from common.utils.generator import LZSDGenerator
from common.config.get_db import get_db
from common.response.response_util import ResponseUtil
from core.deps.auth import get_current_user
from core.deps.token_utils import TokenManager
from core.entity.do.users_do import User, OnlineStatus, WechatLoginState
from core.entity.vo.login_vo import UserLogin
from core.entity.vo.user_schema import ChangePasswordReq
from service.user_service import UserService

loginController = APIRouter()

# =========================
# 微信开放平台配置
# =========================
WECHAT_APP_ID = "wxd81a903a6cff7273"
WECHAT_APP_SECRET = "576e309f6d1e2880a0064ac864d92cf1"

# 必须是开放平台 网站应用 AppID
APP_ID = "wxd81a903a6cff7273"

# ⚠️ 必须 HTTPS + 已配置回调域名
REDIRECT_URI = "http://wenyuanai.com/novelAi/#/wxCallback"


class UserRegisterRequest(BaseModel):
    # 基础注册信息
    account: str = Field(
        ...,
        min_length=4,
        max_length=64,
        description="账号"
    )

    password: str = Field(
        ...,
        min_length=6,
        max_length=64,
        description="密码"
    )

    nickname: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="昵称"
    )

    # 微信注册时携带（普通注册可不传）
    openid: Optional[str] = Field(
        default=None,
        max_length=64,
        description="微信openid"
    )

    unionid: Optional[str] = Field(
        default=None,
        max_length=64,
        description="微信unionid"
    )

@loginController.post('/login', name="登录")
async def login(user_login: UserLogin,
                query_db: AsyncSession = Depends(get_db)):
    """
    用户注册services
    :param user_login: 请求对象
    :param query_db: orm对象
    :param user_login: 登录用户对象
    :return:
    """

    data = await UserService.login(
        db=query_db,
        account=user_login.account,
        password=user_login.password
    )
    # 存储token到map上
    TokenManager.store_token(user_login.account, data)

    return ResponseUtil.success(msg='登录成功', dict_content={'data': data})


@loginController.post("/register", summary="用户注册（支持微信绑定）")
async def register(
    req: UserRegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    注册逻辑：

    普通注册：
        account + password + nickname

    微信注册：
        account + password + nickname
        + openid + unionid
    """

    # =====================================
    # 1️⃣ 校验账号是否存在
    # =====================================
    stmt = select(User).where(User.account == req.account)
    result = await db.execute(stmt)
    exists = result.scalar_one_or_none()

    if exists:
        raise HTTPException(status_code=400, detail="账号已存在")

    # =====================================
    # 2️⃣ 如果传了微信信息，检查是否已绑定
    # =====================================
    if getattr(req, "openid", None):

        stmt = select(User).where(
            User.wechatOpenid == req.openid
        )
        result = await db.execute(stmt)
        bind_user = result.scalar_one_or_none()

        if bind_user:
            raise HTTPException(status_code=400, detail="该微信已注册")

    if getattr(req, "unionid", None):

        stmt = select(User).where(
            User.wechatUnionid == req.unionid
        )
        result = await db.execute(stmt)
        bind_user = result.scalar_one_or_none()

        if bind_user:
            raise HTTPException(status_code=400, detail="该微信已注册")

    # =====================================
    # 3️⃣ 密码加密
    # =====================================
    hashed_password = bcrypt.hashpw(
        req.password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    # =====================================
    # 4️⃣ 创建用户
    # =====================================
    user = User(
        uuid=LZSDGenerator.generate_user_uid(),
        account=req.account,
        nickname=req.nickname,
        avatar="",
        password=hashed_password,
        isBindWechat = True,
        # 微信字段（可为空）
        wechatOpenid=getattr(req, "openid", None),
        wechatUnionid=getattr(req, "unionid", None)
    )

    # =====================================
    # 5️⃣ 入库
    # =====================================
    db.add(user)
    await db.commit()
    await db.refresh(user)

    data = {
        "pkId": user.pkId,
        "uuid": user.uuid,
        "account": user.account,
        "nickname": user.nickname,
    }

    return ResponseUtil.success(data=data)


@loginController.post("/user/changePwd", name="修改密码")
async def change_password(
    req: ChangePasswordReq,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):

    service = UserService()

    await service.change_password(
        db=db,
        account=req.account,
        password=req.password,
        new_password=req.newPassword
    )

    return ResponseUtil.success(msg="密码修改成功")



@loginController.get("/wechat/qr_login")
async def wechat_qr_login(db: AsyncSession = Depends(get_db)):
    state = uuid.uuid4().hex

    # ✅ 关键修复：完整编码
    redirect_uri = quote(REDIRECT_URI, safe="")

    url = (
        "https://open.weixin.qq.com/connect/qrconnect?"
        f"appid={APP_ID}"
        f"&redirect_uri={redirect_uri}"
        "&response_type=code"
        "&scope=snsapi_login"
        f"&state={state}"
        "#wechat_redirect"
    )

    data = {
        "url": url,
        "state": state
    }

    row = WechatLoginState(
        state=state,
        status="waiting",
        expireTime=datetime.utcnow() + timedelta(minutes=5)
    )

    db.add(row)
    await db.commit()

    return ResponseUtil.success(data=data)


@loginController.get("/qr_callback", name="微信扫码回调")
async def qr_callback(
    code: str = "",
    state: str = "",
    db: AsyncSession = Depends(get_db)
):
    if not code:
        raise HTTPException(400, "缺少code")

    # =====================================
    # 1. code 换 access_token / openid
    # =====================================
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.weixin.qq.com/sns/oauth2/access_token",
            params={
                "appid": WECHAT_APP_ID,
                "secret": WECHAT_APP_SECRET,
                "code": code,
                "grant_type": "authorization_code"
            }
        )

    data = resp.json()

    if "errcode" in data:
        raise HTTPException(400, detail=data)

    access_token = data.get("access_token")
    openid = data.get("openid")
    unionid = data.get("unionid")

    # =====================================
    # 2. 查用户
    # =====================================
    user = None

    if unionid:
        result = await db.execute(
            select(User).where(User.wechatUnionid == unionid)
        )
        user = result.scalar_one_or_none()

    if not user:
        result = await db.execute(
            select(User).where(User.wechatOpenid == openid)
        )
        user = result.scalar_one_or_none()

    # =====================================
    # 3. 查询扫码状态
    # =====================================
    login = await db.execute(
        select(WechatLoginState).where(
            WechatLoginState.state == state
        )
    )
    row = login.scalar_one_or_none()

    if not row:
        raise HTTPException(400, "state无效")

    # =====================================
    # 🔥 绑定逻辑（优先处理）
    # =====================================
    if row.status == "bind":

        # 1️⃣ 判断微信是否已被其他账号绑定
        result = await db.execute(
            select(User).where(User.wechatUnionid == unionid)
        )
        exist = result.scalar_one_or_none()

        if exist:
            row.status = "bind_error"
            row.token = json.dumps({"msg": "该微信已绑定其他账号"})
            await db.commit()
            return ResponseUtil.failure(msg="该微信已被用户绑定")

        # 2️⃣ 找当前用户
        result = await db.execute(
            select(User).where(User.pkId == row.user_id)
        )
        bind_user = result.scalar_one_or_none()

        if not bind_user:
            row.status = "bind_error"
            await db.commit()
            return ResponseUtil.failure(msg="用户不存在")

        # 3️⃣ 执行绑定
        bind_user.wechatOpenid = openid
        bind_user.wechatUnionid = unionid
        bind_user.isBindWechat = True
        row.status = "bind_success"

        await db.commit()

        data = {
            "status": "bind_success",
        }
        return ResponseUtil.success(msg='绑定成功', data=data)
    else:

        # =====================================
        # 已注册 → 登录
        # =====================================
        if user:
            access_token_expires = timedelta(minutes=settings.jwt_expire_minutes)
            session_id = str(uuid.uuid4())

            access_token_jwt = await UserService.create_access_token(
                data={
                    "pkId": user.pkId,
                    'uuid': user.uuid,
                    'account': user.account,
                    'nickname': user.nickname,
                    'session_id': session_id,
                    "avatar": user.avatar if user.avatar else "",
                },
                expires_delta=access_token_expires,
            )

            user.onlineStatus = OnlineStatus.ONLINE
            await db.flush()

            data = {
                "status": "login",
                "openid": openid,
                'accessToken': "Bearer " + access_token_jwt,
                "account": user.account,
                "nickname": user.nickname,
                "avatar": user.avatar or ""
            }

            row.status = "login"
            row.openid = openid
            row.unionid = unionid
            row.token = json.dumps(data)

            await db.commit()

            return ResponseUtil.success(msg='登录成功', dict_content={'data': data})

        # =====================================
        # 未注册 → 获取微信用户信息
        # =====================================
        nickname = ""
        avatar = ""

        try:
            async with httpx.AsyncClient() as client:
                user_resp = await client.get(
                    "https://api.weixin.qq.com/sns/userinfo",
                    params={
                        "access_token": access_token,
                        "openid": openid
                    }
                )

            user_info = user_resp.json()

            nickname = user_info.get("nickname", "")


        except Exception as e:
            print("获取微信用户信息失败:", e)

        # =====================================
        # 未注册 → 返回前端注册
        # =====================================
        data = {
            "status": "register",
            "openid": openid,
            "unionid": unionid,
            "nickname": nickname,
            "avatar": avatar
        }
        row.status = "register"
        row.openid = openid
        row.unionid = unionid

        await db.commit()

        return ResponseUtil.success(data=data)

@loginController.get("/wechat/qr_status")
async def qr_status(state: str, db: AsyncSession = Depends(get_db)):

    result = await db.execute(
        select(WechatLoginState).where(
            WechatLoginState.state == state
        )
    )

    row = result.scalar_one_or_none()

    if row and row.status == "register":
        data = {
            "status": "register",
            "openid": row.openid,
            "unionid": row.unionid
        }
        return ResponseUtil.success(data=data)

    elif row and row.status == "login":
        return ResponseUtil.success(msg='登录成功', dict_content={'data': json.loads(row.token)})

    elif row and row.status == "bind_success":
        data = {
            "status": row.status,
        }
        return ResponseUtil.success(msg='绑定成功', data=data)

    elif row and row.status == "bind_error":
        return ResponseUtil.success(msg='绑定失败')

    else:
        data =  {"status": False}
        return ResponseUtil.success(data=data)



@loginController.get("/bind_qr_login", name="用户中心绑定微信")
async def bind_qr_login(
    redirect_url: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)  # 你已有登录鉴权
):
    state = uuid.uuid4().hex

    expire_time = datetime.utcnow() + timedelta(minutes=5)

    row = WechatLoginState(
        state=state,
        status="bind",
        user_id=current_user.pkId,
        expireTime=expire_time
    )

    db.add(row)
    await db.commit()

    url = (
        "https://open.weixin.qq.com/connect/qrconnect?"
        f"appid={WECHAT_APP_ID}"
        f"&redirect_uri={quote(redirect_url if redirect_url else REDIRECT_URI, safe='')}"
        "&response_type=code"
        "&scope=snsapi_login"
        f"&state={state}"
        "#wechat_redirect"
    )

    return ResponseUtil.success(data={
        "state": state,
        "url": url
    })