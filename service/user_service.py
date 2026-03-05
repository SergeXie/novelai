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
