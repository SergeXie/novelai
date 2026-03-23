import jwt
from fastapi import Depends, Header
from jwt import InvalidTokenError
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from common.config.config import settings
from common.config.get_db import get_db
from common.exception.lzsd_exception import ServiceWarning, AuthException
from core.deps.token_utils import TokenManager
from core.entity.do.users_do import AccountStatus, OnlineStatus
from core.entity.vo.user_vo import TokenData
from dao.user_dao import UserDAO
from fastapi import Request


# async def get_login_user(
#     x_user_uuid: str = Header(None, alias="x-User-Uuid"),
#     db: AsyncSession = Depends(get_db)
# ):
#     if not x_user_uuid:
#         raise ServiceWarning(message='请登录！')
#
#     user = await UserDAO.get_by_uuid(db, x_user_uuid)
#
#     if not user:
#         raise ServiceWarning(message='用户已停用')
#
#     if user.onlineStatus == OnlineStatus.OFFLINE:
#         raise ServiceWarning(message="账户已离线请重新登录！")
#
#     return user

async def get_login_user(authorization: str = Header(None, alias="authorization"),
                         query_db: AsyncSession = Depends(get_db)):

    try:
        token = authorization
        if not token:
            raise AuthException(message='Not authorization')
        if token.startswith('@Bearer'):
            return
        else:
            if token.startswith('Bearer'):
                token = token.split(' ')[1]

        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        uuid: str = payload.get('uuid')

        if not uuid:
            logger.warning('用户token不合法')
            raise AuthException(message='用户token不合法')

        token_data = TokenData(uuid=uuid)

    except InvalidTokenError:
        logger.warning('用户凭证已失效，请重新登录！')
        raise AuthException(data='', message='用户token已失效，请重新登录')

    query_user = await UserDAO.get_by_uuid(query_db, user_uuid=token_data.uuid)

    if query_user is None:
        logger.warning('用户token不合法')
        raise AuthException(data='', message='用户token不合法')

    # 从缓存中拿出token
    accessToken = TokenManager.get_account_by_token(query_user.account)

    if token == accessToken:
        return query_user
    else:
        logger.warning('用户凭证已失效，请重新登录')
        raise AuthException(data='', message='用户凭证已失效，请重新登录！')
