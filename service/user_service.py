import bcrypt
from common.exception.lzsd_exception import LoginException, ServiceWarning
from core.entity.do.users_do import OnlineStatus
from dao.user_dao import UserDAO
from sqlalchemy.ext.asyncio import AsyncSession


class UserService:

    @staticmethod
    async def login(
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
            raise ServiceWarning(message="账号或密码错误")

        # 1️⃣ 更新在线状态
        user.onlineStatus = OnlineStatus.ONLINE

        # 3️⃣ 提交（和生成 token 在同一个事务里）
        await db.flush()

        # 登录成功（返回你需要的最小信息）
        return {
            "uuid": user.uuid,
            "account": user.account,
            "nickname": user.nickname
        }
