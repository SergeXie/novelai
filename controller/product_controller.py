from fastapi import APIRouter, Depends
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request
from common.config.get_db import get_db
from common.response.response_util import ResponseUtil
from core.deps.auth import get_login_user
from core.entity.vo.order_schema_vo import CreateOrderRequest, CreateOrderResponse
from core.entity.vo.product_schema_vo import ProductListResponse
from service.account_service import AccountService
from service.order_service import OrderService
from service.payment.payment_service import PaymentService
from service.product_service import ProductService
from urllib.parse import parse_qs

productRouter = APIRouter(prefix="/order")


@productRouter.get("/amounts", name="我的资产")
async def get_account_info(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_login_user),
):
    """
    我的资产信息
    """

    data = await AccountService.get_account_info(db, user.pkId)

    return ResponseUtil.success(data=data)

@productRouter.get("/history", name="历史订购")
async def get_orders_history(
    page: int = 1,
    pageSize: int = 20,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_login_user),
):
    """
    历史订单列表
    """

    data, total = await OrderService.get_order_list(db, user.pkId, page, pageSize)

    return ResponseUtil.success(data=data, dict_content={
            "page": page,
            "pageSize": pageSize,
            "total": total
        })

@productRouter.get("/plans", response_model=ProductListResponse, name="产品列表")
async def get_product_list(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_login_user),
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


@productRouter.post("/pay", response_model=CreateOrderResponse, name="下单")
async def create_order(
    req: CreateOrderRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_login_user),

):
    """
    创建订单接口

    功能：
    - 防重复订单
    - 30分钟过期控制
    - 支持会员/Token包
    """

    result = await OrderService.create_order(
        db=db,
        uid=user.pkId,
        order_type=req.order_type,
        target_code=req.target_code,
        pay_method=req.pay_method
    )

    return ResponseUtil.success(data=result)


@productRouter.post("/callback")
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
