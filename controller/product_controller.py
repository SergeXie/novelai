from fastapi import APIRouter, Depends
from loguru import logger
from openai.types.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession, result
from fastapi import Request

from common.config.config import settings
from common.config.get_db import get_db
from common.response.response_util import ResponseUtil
from core.deps.auth import get_current_user
from core.entity.vo.base_vo import PageResp
from core.entity.vo.order_schema_vo import CreateOrderRequest, CreateOrderResponse
from core.entity.vo.user_vo import BonusGrantListResponse
from service.account_service import AccountService
from service.order_service import OrderService
from service.payment.payment_service import PaymentService
from service.product_service import ProductService

productRouter = APIRouter(prefix="/order")

@productRouter.get("/amounts", name="我的资产")
async def get_amounts(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    我的资产信息
    """

    data = await AccountService.get_account_info(db, user.pkId)

    return ResponseUtil.success(data=data)


@productRouter.get("/bonus/list", name="周五补给列表", response_model=BonusGrantListResponse)
async def get_bonus_list(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    data = await AccountService.get_current_bonus_list(db, user.pkId)
    return ResponseUtil.success(data=data)

@productRouter.get("/history", name="历史订购")
async def get_orders_history(
    page: int = 1,
    pageSize: int = 20,
    startTime: str | None = None,
    endTime: str | None = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    历史订单列表（支持时间筛选）
    """

    data, total = await OrderService.get_order_list(
        db,
        user.pkId,
        page,
        pageSize,
        startTime,
        endTime
    )

    rsp_data = PageResp(
            page=page,
            pageSize=pageSize,
            total=total,
            list=data
        )

    return ResponseUtil.success(data=rsp_data)

@productRouter.get("/plans", response_model=Response, name="产品列表")
async def get_product_list(
    db: AsyncSession = Depends(get_db)
):
    """
    获取产品列表接口

    功能：
    - 返回所有在售会员包
    - 返回所有在售Token包

    使用场景：
    - 前端购买页展示
    - 会员中心
    """

    result = await ProductService.get_product_list(db)
    return ResponseUtil.success(data=result)


@productRouter.post("/pay", name="下单")
async def create_order_(
    req: CreateOrderRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    创建订单接口

    功能：
    - 防重复订单
    - 30分钟过期控制
    - 支持会员/Token包
    """
    if settings.is_dev:
        result = req
        result.return_url = req.return_url + "&code=200"
    else:
        result = await OrderService.create_order(
            db=db,
            user_id=user.pkId,
            order_type=req.order_type,
            target_code=req.target_code,
            pay_method=req.pay_method,
            return_url=req.return_url,
        )

    return ResponseUtil.success(data=result)



@productRouter.get("/status", name="微信订单查询")
async def get_order_status(
    order_no: str,
    db: AsyncSession = Depends(get_db)
):
    """
    查询订单状态
    """

    data = await OrderService.query_order_status(db, order_no)

    if not data:
        return ResponseUtil.failure(msg="订单不存在")

    return ResponseUtil.success(data=data)


@productRouter.post("/callback", name="支付宝回调")
async def alipay_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """
    支付宝异步回调
    """

    async with db.begin():  #  事务开始

        req_json = await request.json()

        raw_body = req_json

        logger.info(f"支付宝回调参数: {raw_body}")

        service = PaymentService()
        result = await service.handle_alipay_callback(db, raw_body)

        if result:
            return "success"
        else:
            return "fail"


@productRouter.post("/wechatCallback", name="微信支付回调")
async def wechat_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """
    微信支付回调
    """

    async with db.begin():  #  事务开始

        body = await request.json()

        logger.info(f"[微信回调] 原始数据: {body}")

        service = PaymentService()

        result = await service.handle_wechat_callback(db, body)

        if result:
            # 微信要求返回这个
            return {"code": "SUCCESS", "message": "成功"}
        else:
            return {"code": "FAIL", "message": "失败"}



@productRouter.get("/qr_callback")
def qr_callback(code: str = "", state: str = ""):
    return {
        "msg": "扫码成功，已回调",
        "code": code,
        "state": state
    }

