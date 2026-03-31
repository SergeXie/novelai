from common.exception.lzsd_exception import ServiceWarning
from service.payment.base_payment import BasePayment
from loguru import logger


class WechatPayService(BasePayment):
    """
    微信支付（占位实现）
    """

    def generate_pay_url(self, order):
        logger.info(f"[微信] 创建支付链接 order_no={order.order_no}")

        # ⚠️ 这里后面接微信支付
        raise ServiceWarning(message="微信支付暂未接入")