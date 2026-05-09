# controller/pv_controller.py

from fastapi import (
    APIRouter,
    Depends,
    Request
)
from loguru import logger

from sqlalchemy.ext.asyncio import AsyncSession
from common.config.get_db import get_db
from common.response.response_util import ResponseUtil
from core.entity.vo.pv_vo import PVCreateRequest
from service.pv_service import PVService

# 创建路由
Pvrouter = APIRouter(
    prefix="/pv",
    tags=["PV统计"]
)


@Pvrouter.post("/create")
async def create_pv(
    request: Request,
    data: PVCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    创建PV访问记录

    :param request: 请求对象
    :param data: 请求参数
    :param db: 数据库会话
    :return:
    """

    # 创建PV日志
    await PVService.create_pv(
        db=db,
        request=request,
        data=data
    )

    logger.info("pv入库成功 请求参数：{}".format(data))

    return ResponseUtil.success()
