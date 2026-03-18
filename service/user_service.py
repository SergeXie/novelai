import uuid
from datetime import timedelta, datetime, timezone
from typing import Union
import bcrypt
import jwt
from common.config.config import settings
from common.exception.lzsd_exception import LoginException, ServiceWarning
from core.entity.do.users_do import OnlineStatus, AccountStatus
from dao.user_dao import UserDAO
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger


class UserService:

    @classmethod
    async def create_access_token(cls, data: dict, expires_delta: Union[timedelta, None] = None):
        """
        根据登录信息创建当前用户token

        :param data: 登录信息
        :param expires_delta: token有效期
        :return: token
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=30)
        to_encode.update({'exp': expire})
        encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        return encoded_jwt

    @classmethod
    async def login(
        cls,
        db: AsyncSession,
        account: str,
        password: str
    ) -> dict:

        user = await UserDAO.get_by_account(db, account)

        if not user:
            raise LoginException(message='账户不存在')

        # bcrypt 校验
        password_ok = bcrypt.checkpw(
            password.encode("utf-8"),
            user.password.encode("utf-8")
        )

        if not password_ok:
            logger.warning(f'用户：{user.account}账号或密码错误')
            raise ServiceWarning(message=f"用户：{user.account}账号或密码错误")

        if user.status != AccountStatus.ACTIVE:
            logger.warning(f'用户：{user.account} 已停用')
            raise LoginException(message='用户已停用')

        access_token_expires = timedelta(minutes=settings.jwt_expire_minutes)
        session_id = str(uuid.uuid4())

        access_token = await cls.create_access_token(
            data={
                'uuid': user.uuid,
                'account': user.account,
                'nickname': user.nickname,
                'session_id': session_id,
            },
            expires_delta=access_token_expires,
        )

        # 1️⃣ 更新在线状态
        user.onlineStatus = OnlineStatus.ONLINE

        # 3️⃣ 提交（和生成 token 在同一个事务里）
        await db.flush()

        # 登录成功（返回你需要的最小信息）
        return {
            'accessToken': "Bearer" + " " + access_token,
            "account": user.account,
            "nickname": user.nickname
        }

    async def change_password(self, db, account: str, password: str, new_password: str):

        # 1 查询用户
        user = await UserDAO.get_by_account(db, account)

        if not user:
            raise ValueError("用户不存在")

        # 2 校验旧密码
        password_ok = bcrypt.checkpw(
            password.encode("utf-8"),
            user.password.encode("utf-8")
        )

        if not password_ok:
            raise ServiceWarning("原密码错误")

        # 3 加密新密码
        hashed_password = bcrypt.hashpw(
            new_password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode()

        # 4 更新密码
        await UserDAO.update_password(
            db,
            user.pkId,
            hashed_password
        )

        return True



