from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from common.config.get_db import get_db
from common.response.response_util import ResponseUtil
from core.entity.vo.login_vo import UserLogin
from service.user_service import UserService

loginController = APIRouter()


@loginController.post('/login', name="登录")
async def login(user_login: UserLogin,
                query_db: AsyncSession = Depends(get_db)):
    """
    用户注册services
    :param request: 请求对象
    :param query_db: orm对象
    :param user_login: 登录用户对象
    :return:
    """

    data = await UserService.login(
        db=query_db,
        account=user_login.account,
        password=user_login.password
    )

    return ResponseUtil.success(msg='登录成功', dict_content={'data': data})
