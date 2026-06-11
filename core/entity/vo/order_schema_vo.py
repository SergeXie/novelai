from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_serializer


class CreateOrderRequest(BaseModel):
    """创建订单请求参数。"""

    order_type: str          # MEMBERSHIP / TOKEN_PACKAGE
    target_code: str         # 商品编码
    pay_method: str          # alipay / wechat
    return_url: str


class CreateOrderResponse(BaseModel):
    """创建订单返回结构。"""

    order_no: str
    pay_method: str
    amount: float
    pay_url: str
    return_url: str


class CreateInternalOrderRequest(BaseModel):
    """内部下单请求参数，会直接创建已支付订单并发放权益。"""

    order_type: str
    target_code: str
    user_id: Optional[int] = None
    pay_amount: float = 0
    remark: Optional[str] = None


class CreateInternalOrderResponse(BaseModel):
    """内部下单返回结构。"""

    order_no: str
    order_type: str
    target_code: str
    user_id: int
    total_amount: float
    pay_amount: float
    pay_method: str
    status: str
    paid_at: Optional[str] = None


class OrderListItem(BaseModel):
    """历史订单项。"""

    order_no: str
    order_type: str
    name: str
    total_amount: float
    pay_amount: float
    status: str
    paid_at: Optional[str] = None
    pay_method: str
    created_at: Optional[datetime] = None

    @field_serializer("created_at")
    def serialize_created_at(self, created_at: datetime | None, _info):
        if created_at is None:
            return None
        return created_at.strftime("%Y-%m-%d %H:%M:%S")


class OrderListResponse(BaseModel):
    """订单列表返回结构。"""

    list: list[OrderListItem]
    total: int
