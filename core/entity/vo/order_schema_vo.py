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