from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from common.config.get_db import get_db
from common.exception.lzsd_exception import ServiceWarning
from core.entity.do.users_do import AccountStatus, OnlineStatus
from dao.user_dao import UserDAO


async def get_login_user(
    x_user_uuid: str = Header(None, alias="x-User-Uuid"),
    db: AsyncSession = Depends(get_db)
):
    if not x_user_uuid:
        raise ServiceWarning(message='请登录！')

    user = await UserDAO.get_by_uuid(db, x_user_uuid)

    if not user:
        raise ServiceWarning(message='用户已停用')

    if user.onlineStatus == OnlineStatus.OFFLINE:
        raise ServiceWarning(message="账户已离线请重新登录！")

    return user
