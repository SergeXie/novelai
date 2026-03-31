from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CreateOrderRequest(BaseModel):
    """
    创建订单请求参数
    """
    order_type: str          # MEMBERSHIP / TOKEN_PACKAGE
    target_code: str         # 商品编码
    pay_method: str          # alipay / wechat


class CreateOrderResponse(BaseModel):
    """
    创建订单返回结构
    """
    order_no: str
    pay_method: str
    amount: float
    pay_url: str


class OrderListItem(BaseModel):
    """
    历史订单项
    """

    order_no: str
    order_type: str
    name: str
    total_amount: float
    pay_amount: float
    status: str
    paid_at: Optional[datetime] = None
    pay_method:str


class OrderListResponse(BaseModel):
    """
    订单列表返回
    """

    list: list[OrderListItem]
    total: int