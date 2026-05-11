# dao/pv_dao.py
from sqlalchemy.ext.asyncio import AsyncSession
from core.entity.do.pv_log_do import McPVLog


class PVDao:

    @staticmethod
    async def create(
        db: AsyncSession,
        data: dict
    ):
        """
        创建PV日志

        :param db: 数据库会话
        :param data: PV数据
        :return:
        """

        # 创建ORM对象
        pv = McPVLog(**data)

        # 添加到数据库
        db.add(pv)

        # 提交事务
        await db.commit()

        # 刷新对象
        await db.refresh(pv)

        return pv