from urllib.parse import parse_qsl
import json

from fastapi import APIRouter, Depends, Header, Request
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from common.config.config import settings
from common.config.get_db import get_db
from common.exception.lzsd_exception import ServiceWarning
from common.response.response_util import ResponseUtil
from core.deps.auth import get_current_user
from core.entity.vo.base_vo import PageResp
from core.entity.vo.order_schema_vo import CreateInternalOrderRequest, CreateOrderRequest
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
    data, total = await OrderService.get_order_list(
        db,
        user.pkId,
        page,
        pageSize,
        startTime,
        endTime,
    )

    rsp_data = PageResp(
        page=page,
        pageSize=pageSize,
        total=total,
        list=data,
    )
    return ResponseUtil.success(data=rsp_data)


@productRouter.get("/plans", name="产品列表")
async def get_product_list(
    db: AsyncSession = Depends(get_db),
):
    result = await ProductService.get_product_list(db)
    return ResponseUtil.success(data=result)


@productRouter.post("/pay", name="下单")
async def create_order_(
    req: CreateOrderRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
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



@productRouter.post("/internal/pay", name="内部下单")
async def create_internal_order(
    req: CreateInternalOrderRequest,
    x_internal_token: str | None = Header(None, alias="X-Internal-Token"),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    if settings.INTERNAL_ORDER_SECRET:
        if x_internal_token != settings.INTERNAL_ORDER_SECRET:
            raise ServiceWarning("内部下单密钥错误")
    elif settings.is_prod:
        raise ServiceWarning("生产环境未配置 INTERNAL_ORDER_SECRET，禁止内部下单")

    target_user_id = req.user_id or user.pkId
    result = await OrderService.create_internal_order(
        db=db,
        user_id=target_user_id,
        order_type=req.order_type,
        target_code=req.target_code,
        operator_user_id=user.pkId,
        pay_amount=req.pay_amount,
        remark=req.remark,
    )

    return ResponseUtil.success(data=result)


@productRouter.get("/status", name="订单查询")
async def get_order_status(
    order_no: str,
    db: AsyncSession = Depends(get_db),
):
    data = await OrderService.query_order_status(db, order_no)

    if not data:
        return ResponseUtil.failure(msg="订单不存在")

    return ResponseUtil.success(data=data)


def _parse_alipay_callback_body(content_type: str, raw_payload) -> dict:
    if isinstance(raw_payload, dict):
        return raw_payload

    if isinstance(raw_payload, bytes):
        raw_payload = raw_payload.decode("utf-8")

    if isinstance(raw_payload, str):
        raw_payload = raw_payload.strip()
        if raw_payload.startswith('"') and raw_payload.endswith('"'):
            try:
                raw_payload = json.loads(raw_payload)
            except json.JSONDecodeError:
                raw_payload = raw_payload[1:-1]
        return dict(parse_qsl(raw_payload, keep_blank_values=True))

    logger.warning(f"[支付宝回调] 不支持的参数类型: {type(raw_payload)} content_type={content_type}")
    return {}


@productRouter.post("/callback", name="支付宝回调")
async def alipay_callback(request: Request, db: AsyncSession = Depends(get_db)):
    async with db.begin():
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = await request.json()
        else:
            payload = await request.body()

        callback_data = _parse_alipay_callback_body(content_type, payload)
        logger.info(f"支付宝回调参数: {callback_data}")

        service = PaymentService()
        result = await service.handle_alipay_callback(db, callback_data)

        return "success" if result else "fail"


@productRouter.post("/wechatCallback", name="微信支付回调")
async def wechat_callback(request: Request, db: AsyncSession = Depends(get_db)):
    async with db.begin():
        body = await request.json()
        logger.info(f"[微信回调] 原始数据: {body}")

        service = PaymentService()
        result = await service.handle_wechat_callback(db, body)

        if result:
            return {"code": "SUCCESS", "message": "成功"}
        return {"code": "FAIL", "message": "失败"}


@productRouter.get("/qr_callback")
def qr_callback(code: str = "", state: str = ""):
    return {
        "msg": "扫码成功，已回调",
        "code": code,
        "state": state,
    }
