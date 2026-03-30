from fastapi import APIRouter, Depends
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request
from common.config.get_db import get_db
from common.response.response_util import ResponseUtil
from core.deps.auth import get_login_user
from core.entity.vo.order_schema_vo import CreateOrderRequest, CreateOrderResponse
from core.entity.vo.product_schema_vo import ProductListResponse
from service.order_service import OrderService
from service.payment.payment_service import PaymentService
from service.product_service import ProductService
from urllib.parse import parse_qs

productRouter = APIRouter(prefix="/order")


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

    return await OrderService.create_order(
        db=db,
        uid=user.pkId,
        order_type=req.order_type,
        target_code=req.target_code,
        pay_method=req.pay_method
    )


@productRouter.post("/callback")
async def alipay_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """
    支付宝异步回调
    """
    req_json = await request.json()

    raw_body = req_json

    logger.info(f"🔥 raw_body: {raw_body}")


    # try:
    service = PaymentService()
    result = await service.handle_alipay_callback(db, raw_body)

    if result:
        return "success"
    else:
        return "fail"

    # except Exception as e:
    #     logger.error(f"[回调] 处理失败 err={e}")
    #     return "fail"
