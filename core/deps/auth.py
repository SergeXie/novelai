import jwt
from fastapi import Depends, Header
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from common.config.config import settings
from common.config.get_db import get_db, get_db_context
from common.exception.lzsd_exception import AuthException, IllegalBookAccessException, InsufficientTokenException
from core.entity.do.users_do import User
from core.entity.vo.login_vo import CurrentUser
from dao.ai_model_dao import AiModelDAO
from dao.book_dao import BookDAO
from dao.user_account_dao import UserAccountDAO
from dao.user_dao import UserDAO
from service.account_service import AccountService
from service.usage_service import UsageService


async def get_current_user(
    authorization: str = Header(None),
    dev: str = Header(None),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser | None:
    """Parse the current user from Authorization header."""
    try:
        if settings.ENV_MODE == "development" and dev:
            logger.info(f"{dev} is authenticated by dev header")
            user = await UserDAO.get_by_account(db, account=dev)
            if user:
                return user
            raise AuthException(message="Not authorization")

        token = authorization
        if not token:
            raise AuthException(message="Not authorization")

        if token.startswith("@Bearer"):
            return None

        if token.startswith("Bearer"):
            token = token.split(" ")[1]

        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        uuid: str = payload.get("uuid")
        pkId: str = payload.get("pkId")
        account: str = payload.get("account")
        nickname: str = payload.get("nickname")
        avatar: str = payload.get("avatar")

        if not uuid and not pkId:
            logger.warning("Invalid user token")
            raise AuthException(message="用户token不合法")

        return CurrentUser(pkId=pkId, uuid=uuid, account=account, nickname=nickname, avatar=avatar)

    except Exception as exc:
        logger.warning(f"User auth failed: {exc}")
        raise AuthException(data="", message="用户token已失效，请重新登录")


async def check_book_owner(
    bid: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    book_dao = BookDAO(db)
    book = await book_dao.get_book_by_bid(user_id=user.pkId, bid=bid)

    if not book:
        raise IllegalBookAccessException()


async def check_user_quota_or_raise(frozen_token_length: int, user_info: User, level=None):
    """
    Validate whether the user has enough quota for a generation request.

    Priority:
    1. Paid account balance: monthly + bonus + permanent.
    2. Monthly free quota.
    """
    if frozen_token_length <= 0:
        pass
    
    user_id = user_info.pkId

    async with get_db_context() as db:
        usage_service = UsageService(db)

        account = await UserAccountDAO.get_active_account(db=db, user_id=user_id)
        if not account:
            account = await AccountService.init_account(db, user_id)
        await AccountService.ensure_monthly_free_allowance(db, account)

        user_paid_balance = (
            (account.monthly_balance or 0)
            + (account.bonus_balance or 0)
            + (account.redeem_balance or 0)
            + (account.permanent_balance or 0)
        ) if account else 0
        user_free_balance = (account.free_balance or 0) if account else 0

        user_level = AccountService.get_user_level(account) if account else "free"
        if user_level == "free" and level:
            if level not in [0, 2]:
                raise InsufficientTokenException("免费用户只能使用执笔与才女模型")

        model_multiplier = 1
        if level is not None:
            model = await AiModelDAO(db).get_model_by_level(level)
            if model:
                model_multiplier = float(model.multiplier or 1)

        estimated_amount = int(frozen_token_length * settings.MULTIPLIER)
        estimated_asset_amount = int(estimated_amount * model_multiplier)

        if user_paid_balance >= estimated_asset_amount:
            return

        needed_from_free = estimated_asset_amount - user_paid_balance
        if user_free_balance < needed_from_free:
            logger.info(
                f"User monthly free balance insufficient: {user_info.account}, "
                f"need={needed_from_free}, free_balance={user_free_balance}"
            )
            raise InsufficientTokenException("您的个人每月免费额度不足")

        platform_total = await usage_service.get_platform_daily_consumption()
        if platform_total + needed_from_free > settings.PLATFORM_DAILY_TOKEN_LIMIT:
            logger.error(f"Platform limit reached: {user_info.account}")
            raise InsufficientTokenException("系统今日总额度已耗尽")

