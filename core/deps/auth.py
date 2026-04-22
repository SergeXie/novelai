import jwt
from fastapi import Depends, Header
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from common.config.config import settings
from common.config.get_db import get_db, get_db_context
from common.exception.lzsd_exception import AuthException, IllegalBookAccessException, InsufficientTokenException
from core.entity.do.users_do import User
from core.entity.vo.login_vo import CurrentUser
from dao.book_dao import BookDAO
from dao.user_dao import UserDAO
from service.account_service import AccountService
from service.usage_service import UsageService


async def get_current_user(
    authorization: str = Header(None),
    dev: str = Header(None),
    db: AsyncSession = Depends(get_db)  # 优先使用注入的 Session
) -> CurrentUser| None:

    ### 根据header中token获取当前用户
    try:
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

        token = authorization
        if not token:
            raise AuthException(message='Not authorization')

        if token.startswith('@Bearer'):
            return None
        else:
            if token.startswith('Bearer'):
                token = token.split(' ')[1]

        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        uuid: str = payload.get('uuid')
        pkId: str = payload.get('pkId')
        account: str = payload.get('account')
        nickname: str = payload.get('nickname')
        if not uuid and not pkId:
            logger.warning('用户token不合法')
            raise AuthException(message='用户token不合法')

        # token_data = TokenData(uuid=uuid)
        # 直接构造用户（不查数据库）
        return CurrentUser(pkId=pkId, uuid=uuid, account=account, nickname=nickname)

    except Exception as _:
        logger.warning('用户凭证已失效，请重新登录！')
        raise AuthException(data='', message='用户token已失效，请重新登录')

    # query_user = await UserDAO.get_by_uuid(db, user_uuid=token_data.uuid)
    #
    # if query_user is None:
    #     logger.warning('用户token不合法')
    #     raise AuthException(data='', message='用户token不合法')

    # 重启服务器不要丢失已登录的用户状态
    # 从缓存中拿出token
    # access_token = TokenManager.get_account_by_token(query_user.account)
    #
    # if token == access_token:
    #     return query_user
    # else:
    #     logger.warning('用户凭证已失效，请重新登录')
    #     raise AuthException(data='', message='用户凭证已失效，请重新登录！')

    return query_user


async def check_book_owner( bid: str,  db: AsyncSession = Depends(get_db), user=Depends(get_current_user)) :
    book_dao = BookDAO(db)
    book = await book_dao.get_book_by_bid(user_id=user.pkId, bid=bid)

    if not book:
        raise IllegalBookAccessException()


async def check_user_quota_or_raise(frozen_token_length: int, user_info: User, level=None):
    """
    有三个地方需要检查
    -- ai工具调用render
    -- 推理 generate
    -- 一键成书工作流
    -- level模型等级（免费用户只能用执笔和才女）
    """

    user_id = user_info.pkId
    async with get_db_context() as db:
        usage_service = UsageService(db)

        # 1. 获取付费账户余额
        account = await AccountService.get_account_info(db=db, user_id=user_id)
        user_paid_balance = account.total_amount if account else 0

        if account.level == "free" and level:
            if level not in [0, 2]:  # TODO 0 执笔 2 才女
                raise InsufficientTokenException("免费用户只能使用执笔与才女")

        # 情况 A：付费额度充足，直接放行 (这是最快的路径)
        if user_paid_balance >= frozen_token_length:
            return

        # 情况 B：付费额度不足，需要消耗“免费/每日”配额
        # 计算还需要从免费配额中抵扣的“原始 Token 数”
        needed_from_free = frozen_token_length - user_paid_balance

        # 转换为加权后的额度（用于与 Limit 比较）
        weighted_needed = int(needed_from_free * settings.MULTIPLIER)

        # 2. 检查平台总限额 (全局熔断)
        platform_total = await usage_service.get_platform_daily_consumption()
        if platform_total + weighted_needed > settings.PLATFORM_DAILY_TOKEN_LIMIT:
            logger.error(f"Platform limit reached: {user_info.account}")
            raise InsufficientTokenException("系统今日总额度已耗尽")

        # 3. 检查个人每日限额
        input_total, output_total = await usage_service.get_user_daily_input_output(user_id)
        # 个人已消耗的加权额度 (假设数据库里存的是原始值)
        user_already_consumed_weighted = (input_total + output_total) * settings.MULTIPLIER

        if (user_already_consumed_weighted + weighted_needed) > settings.USER_DAILY_TOKEN_LIMIT:
            logger.info(
                f"User limit reached: {user_info.account}, Total: {user_already_consumed_weighted + weighted_needed}")
            raise InsufficientTokenException("您的个人每日免费额度不足")