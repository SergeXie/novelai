# service/pv_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request
from core.entity.vo.pv_vo import PVCreateRequest
from dao.pv_dao import PVDao


class PVService:

    @staticmethod
    async def create_pv(
        db: AsyncSession,
        request: Request,
        data: PVCreateRequest,
    ):
        """
        创建PV记录

        :param db: 数据库会话
        :param request: 请求对象
        :param data: 前端传递的数据
        :return:
        """

        # 1️⃣ 把 Pydantic 模型转换为 dict
        # exclude_unset=True 只保留前端实际传的字段，避免 None 覆盖默认值
        pv_data = data.dict(exclude_unset=True)

        # 2️⃣ 后端动态字段
        pv_data.update({
            "ip": request.client.host,  # 自动获取访问IP
        })
        
        # 调用DAO层创建数据
        return await PVDao.create(
            db=db,
            data=pv_data
        )