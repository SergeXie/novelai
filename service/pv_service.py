# service/pv_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request
from dao.pv_dao import PVDao


class PVService:

    @staticmethod
    async def create_pv(
        db: AsyncSession,
        request: Request,
        data
    ):
        """
        创建PV记录

        :param db: 数据库会话
        :param request: 请求对象
        :param data: 前端传递的数据
        :return:
        """

        # 获取客户端IP
        ip = request.client.host

        # 组装入库数据
        pv_data = {
            "visitor_id": data.visitor_id,
            "page": data.page,
            "browser": data.browser,
            "ip": ip,
            "device": data.device,
            "referer": data.referer,
            "user_agent": data.user_agent
        }

        # 调用DAO层创建数据
        return await PVDao.create(
            db=db,
            data=pv_data
        )