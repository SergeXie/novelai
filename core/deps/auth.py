import jwt
from fastapi import Depends, Header, Body, HTTPException
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from common.config.config import settings
from common.config.get_db import get_db
from common.exception.lzsd_exception import AuthException
from core.deps.token_utils import TokenManager
from core.entity.do.books import Book
from core.entity.schemas import GenerateRequest
from core.entity.vo.user_vo import TokenData
from dao.book_dao import BookDAO
from dao.user_dao import UserDAO


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
                         dev: str = Header(None, alias="dev"),
                         query_db: AsyncSession = Depends(get_db)):

    try:
        token = authorization
        if not token:
            raise AuthException(message='Not authorization')

        # --- 调试模式后门 ---
        # 如果开启了调试模式，且 Token 不是以 Bearer 开头，尝试将其视作 account 直接查询
        if settings.ENV_MODE == "development":
            if dev:
                # 调试时直接在 Header 填入用户账号，如 "test"
                query_user = await UserDAO.get_by_account(query_db, account=dev)
                if query_user:
                    return query_user
        # ------------------

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

    except Exception as e:
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


async def check_book_owner(
    request: GenerateRequest,   # ✅ 直接拿整个请求体
    db: AsyncSession = Depends(get_db),
    user=Depends(get_login_user)
) -> Book:
    book_dao = BookDAO(db)
    book = await book_dao.get_book_by_bid(
        user_id=user.pkId,
        bid=request.bid
    )

    if not book:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="书籍不存在或无权访问"
        )
    return book