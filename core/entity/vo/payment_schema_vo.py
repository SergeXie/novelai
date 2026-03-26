from pydantic import BaseModel


class PayResponse(BaseModel):
    """
    支付返回结构
    """
    order_no: str
    pay_url: str