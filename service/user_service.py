import uuid
from datetime import datetime, timedelta, timezone
from typing import Union
from urllib.parse import urlparse

import bcrypt
import jwt
from loguru import logger
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from common.config.config import settings
from common.exception.lzsd_exception import LoginException, SensitiveWordException, ServiceWarning
from core.entity.do.users_do import AccountStatus, OnlineStatus, User
from dao.user_dao import UserDAO
from service.account_service import AccountService
from service.content_audit_service import get_content_audit_service


class UserService:
    @staticmethod
    def normalize_avatar_path(avatar_url: str) -> str:
        """
        Store only the resource path in DB, for example:
        http://host/files/a.jpg -> /files/a.jpg
        """
        avatar_url = avatar_url.strip()
        if not avatar_url:
            raise ServiceWarning("头像地址不能为空")

        parsed_url = urlparse(avatar_url)
        avatar_path = parsed_url.path if parsed_url.scheme and parsed_url.netloc else avatar_url
        avatar_path = avatar_path.strip()

        if not avatar_path:
            raise ServiceWarning("头像地址无效")

        if not avatar_path.startswith("/"):
            avatar_path = f"/{avatar_path}"

        if len(avatar_path) > 512:
            raise ServiceWarning("头像地址不能超过512个字符")

        return avatar_path

    @staticmethod
    def build_avatar_url(avatar_path: str | None) -> str:
        """
        Convert the stored avatar path back to a public URL for API responses.
        Existing full URLs are returned as-is for backward compatibility.
        """
        if not avatar_path:
            return ""

        if avatar_path.startswith("http://") or avatar_path.startswith("https://"):
            return avatar_path

        cloud_address = (settings.CLOUD_ADDRESS or "").rstrip("/")
        if not cloud_address:
            return avatar_path

        return f"{cloud_address}/{avatar_path.lstrip('/')}"

    @staticmethod
    async def update_nickname(
        db: AsyncSession,
        user_id: str,
        nickname: str,
    ):
        """Update user nickname after basic validation and sensitive word check."""
        nickname = nickname.strip()

        if not nickname:
            raise ServiceWarning("昵称不能为空")

        audit_service = get_content_audit_service()
        result = audit_service.assert_safe_instruction_dfa_only(text=nickname)
        if not result.passed:
            raise SensitiveWordException(message=result.reason)

        if len(nickname) > 20:
            raise ServiceWarning("昵称不能超过20个字符")

        stmt = (
            update(User)
            .where(User.pkId == user_id)
            .values(nickname=nickname)
        )
        result = await db.execute(stmt)

        if result.rowcount == 0:
            raise ServiceWarning("用户不存在")

        logger.info(f"[用户] 修改昵称 uid={user_id}, nickname={nickname}")
        return True

    @staticmethod
    async def update_avatar(
        db: AsyncSession,
        userId: int,
        avatar_url: str,
    ) -> str:
        """Update avatar and store only the normalized resource path."""
        avatar_path = UserService.normalize_avatar_path(avatar_url)

        stmt = (
            update(User)
            .where(User.pkId == userId)
            .values(avatar=avatar_path)
        )
        result = await db.execute(stmt)

        if result.rowcount == 0:
            raise ServiceWarning("用户不存在")

        logger.info(f"[用户] 修改头像 uid={userId}, avatar={avatar_path}")
        return avatar_path

    @classmethod
    async def create_access_token(cls, data: dict, expires_delta: Union[timedelta, None] = None):
        """Create JWT access token from login payload."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=30)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        return encoded_jwt

    @classmethod
    async def login(
        cls,
        db: AsyncSession,
        account: str,
        password: str,
    ) -> dict:
        user = await UserDAO.get_by_account(db, account)

        if not user:
            raise LoginException(message="账号不存在")

        password_ok = bcrypt.checkpw(
            password.encode("utf-8"),
            user.password.encode("utf-8"),
        )

        if not password_ok:
            logger.warning(f"用户 {user.account} 账号或密码错误")
            raise ServiceWarning(message=f"用户 {user.account} 账号或密码错误")

        if user.status != AccountStatus.ACTIVE:
            logger.warning(f"用户 {user.account} 已停用")
            raise LoginException(message="用户已停用")

        access_token_expires = timedelta(minutes=settings.jwt_expire_minutes)
        session_id = str(uuid.uuid4())

        access_token = await cls.create_access_token(
            data={
                "pkId": user.pkId,
                "uuid": user.uuid,
                "account": user.account,
                "nickname": user.nickname,
                "session_id": session_id,
                "avatar": user.avatar if user.avatar else "",
            },
            expires_delta=access_token_expires,
        )

        user.onlineStatus = OnlineStatus.ONLINE
        await AccountService.claim_due_bonus_plans(db, user.pkId)
        await db.flush()

        return {
            "accessToken": "Bearer" + " " + access_token,
            "account": user.account,
            "nickname": user.nickname,
        }

    async def change_password(self, db, account: str, password: str, new_password: str):
        user = await UserDAO.get_by_account(db, account)

        if not user:
            raise ValueError("用户不存在")

        password_ok = bcrypt.checkpw(
            password.encode("utf-8"),
            user.password.encode("utf-8"),
        )

        if not password_ok:
            raise ServiceWarning("原密码错误")

        hashed_password = bcrypt.hashpw(
            new_password.encode("utf-8"),
            bcrypt.gensalt(),
        ).decode()

        await UserDAO.update_password(
            db,
            user.pkId,
            hashed_password,
        )

        return True
