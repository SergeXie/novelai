import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.utils.generator import LZSDGenerator
from common.config.get_db import get_db
from common.response.response_util import ResponseUtil
from core.deps.auth import get_current_user
from core.deps.token_utils import TokenManager
from core.entity.do.users_do import User
from core.entity.vo.login_vo import UserLogin
from core.entity.vo.user_schema import ChangePasswordReq
from service.user_service import UserService

loginController = APIRouter()


class UserRegisterRequest(BaseModel):
    account: str = Field(..., min_length=4, max_length=64)
    password: str = Field(..., min_length=6, max_length=64)
    nickname: str = Field(..., min_length=1, max_length=64)


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


@loginController.post("/register", summary="用户注册")
async def register(
    req: UserRegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    用户注册接口
    - account 唯一
    - password 使用 bcrypt + salt
    """

    # 1️⃣ 校验账号是否存在
    stmt = select(User).where(User.account == req.account)
    result = await db.execute(stmt)
    exists = result.scalar_one_or_none()

    if exists:
        raise HTTPException(status_code=400, detail="账号已存在")

    # 2️⃣ 密码加盐哈希
    hashed_password = bcrypt.hashpw(
        req.password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    # 3️⃣ 创建用户
    user = User(
        uuid=LZSDGenerator.generate_user_uid(),
        account=req.account,
        nickname=req.nickname,
        password=hashed_password
    )

    # 4️⃣ 入库
    db.add(user)
    await db.commit()
    await db.refresh(user)

    data =  {
        "pkId": user.pkId,
        "uuid": user.uuid,
        "account": user.account,
        "nickname": user.nickname
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
