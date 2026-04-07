import jwt
from fastapi import Depends, Header
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from common.config.config import settings
from common.config.get_db import get_db
from common.exception.lzsd_exception import AuthException, IllegalBookAccessException
from core.deps.token_utils import TokenManager
from core.entity.do.users_do import User
from core.entity.vo.user_vo import TokenData
from dao.book_dao import BookDAO
from dao.user_dao import UserDAO

async def get_current_user(
    authorization: str = Header(None),
    dev: str = Header(None),
    db: AsyncSession = Depends(get_db)  # 优先使用注入的 Session
) -> User| None:

    ### 根据header中token获取当前用户
    try:
        token = authorization
        if not token:
            raise AuthException(message='Not authorization')

        # --- 调试模式后门 ---
        # 如果开启了调试模式，且 Token 不是以 Bearer 开头，尝试将其视作 account 直接查询
        if settings.ENV_MODE == "development":
            if dev:
                print(f"{dev} is authenticated")
                user = await UserDAO.get_by_account(db, account=dev)
                if user:
                    return user
                else:
                    raise AuthException(message='Not authorization')

        # ------------------

        if token.startswith('@Bearer'):
            return None
        else:
            if token.startswith('Bearer'):
                token = token.split(' ')[1]

        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        uuid: str = payload.get('uuid')

        if not uuid:
            logger.warning('用户token不合法')
            raise AuthException(message='用户token不合法')

        token_data = TokenData(uuid=uuid)

    except Exception as _:
        logger.warning('用户凭证已失效，请重新登录！')
        raise AuthException(data='', message='用户token已失效，请重新登录')

    query_user = await UserDAO.get_by_uuid(db, user_uuid=token_data.uuid)

    if query_user is None:
        logger.warning('用户token不合法')
        raise AuthException(data='', message='用户token不合法')

    # 从缓存中拿出token
    access_token = TokenManager.get_account_by_token(query_user.account)

    if token == access_token:
        return query_user
    else:
        logger.warning('用户凭证已失效，请重新登录')
        raise AuthException(data='', message='用户凭证已失效，请重新登录！')


async def check_book_owner( bid: str,  db: AsyncSession = Depends(get_db), user=Depends(get_current_user)) :
    book_dao = BookDAO(db)
    book = await book_dao.get_book_by_bid(user_id=user.pkId, bid=bid)

    if not book:
        raise IllegalBookAccessException()