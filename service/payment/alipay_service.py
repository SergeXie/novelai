from alipay import AliPay
from loguru import logger

from common.config.config import settings
from service.payment.base_payment import BasePayment


class AlipayService(BasePayment):
    """
    支付宝支付实现
    """

    def __init__(self):
        self.alipay = AliPay(
            appid=settings.ALIPAY_APP_ID,
            app_notify_url=settings.ALIPAY_NOTIFY_URL,
            app_private_key_string=open(settings.ALIPAY_PRIVATE_KEY).read(),
            alipay_public_key_string=open(settings.ALIPAY_PUBLIC_KEY).read(),
            sign_type="RSA2",
            debug=True
        )

    def generate_pay_url(self, order) -> str:
        """
        生成支付宝支付链接
        """
        logger.info(f"[支付宝] 开始生成支付链接 order_no={order.order_no}")

        try:
            order_string = self.alipay.api_alipay_trade_page_pay(
                out_trade_no=order.order_no,
                total_amount=str(order.pay_amount),
                subject=order.snapshot_name,
                return_url=settings.ALIPAY_RETURN_URL,
                notify_url=settings.ALIPAY_NOTIFY_URL
            )

            # pay_url = f"https://openapi.alipaydev.com/gateway.do?{order_string}"

            logger.info(f"[支付宝] 生成支付成功 order_no={order.order_no}")

            return f"{settings.ALIPAY_GATEWAY}?{order_string}"

        except Exception as e:
            logger.error(f"[支付宝] 生成支付失败 order_no={order.order_no}, err={e}")
            raise