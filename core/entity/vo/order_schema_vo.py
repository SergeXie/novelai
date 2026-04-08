from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_serializer


class CreateOrderRequest(BaseModel):
    """
    创建订单请求参数
    """
    order_type: str          # MEMBERSHIP / TOKEN_PACKAGE
    target_code: str         # 商品编码
    pay_method: str          # alipay / wechat
    return_url: str


class CreateOrderResponse(BaseModel):
    """
    创建订单返回结构
    """
    order_no: str
    pay_method: str
    amount: float
    pay_url: str
    return_url:str

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
    created_at: Optional[datetime] = None

    @field_serializer('paid_at')
    def serialize_paid_at(self, paid_at: Optional[datetime], _info):
        if paid_at is None:
            return None
        # 这里定义你想要的格式，例如：2026-03-31 11:05:22
        return paid_at.strftime('%Y-%m-%d %H:%M:%S')

    @field_serializer('created_at')
    def serialize_created_at(self, created_at: datetime | None, _info):
        if created_at is None:
            return None
        return created_at.strftime('%Y-%m-%d %H:%M:%S')


class OrderListResponse(BaseModel):
    """
    订单列表返回
    """

    list: list[OrderListItem]
    total: int