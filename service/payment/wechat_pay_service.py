import json
import logging

from loguru import logger
from wechatpayv3.async_ import AsyncWeChatPay, WeChatPayType
from common.config.config import settings
from common.exception.lzsd_exception import ServiceWarning
from service.payment.base_payment import BasePayment


class WechatPayService(BasePayment):
    """
    微信支付实现（Native二维码）
    """

    async def generate_pay_url(self, order):
        """
        生成微信支付二维码链接
        """

        logger.info(f"[微信] 创建支付链接 order_no={order.order_no}")

        # ==================== 1. 读取私钥 ====================

        PRIVATE_KEY = open(settings.WECHATPAY_PRIVATE_KEY_PATH).read()
        PUBLIC_KEY = open(settings.PUBLIC_KEY).read()

        # ==================== 2. 创建客户端 ====================

        async with AsyncWeChatPay(
            wechatpay_type=WeChatPayType.NATIVE,
            mchid=settings.WECHATPAY_MCHID,
            private_key=PRIVATE_KEY,
            cert_serial_no=settings.WECHATPAY_CERT_SERIAL_NO,
            apiv3_key=settings.WECHATPAY_APIV3_KEY,
            appid=settings.WECHATPAY_APPID,
            notify_url=settings.WECHATPAY_NOTIFY_URL,
            cert_dir=settings.WECHATPAY_CERT_DIR,
            partner_mode=False,  # 普通商户（直连模式）
            public_key=PUBLIC_KEY,
            public_key_id=settings.PUBLIC_KEY_ID

        ) as wxpay:

            # ==================== 3. 下单 ====================

            code, message = await wxpay.pay(
                description=order.snapshot_name,
                out_trade_no=order.order_no,
                amount={
                    "total": int(order.pay_amount * 100)  #  元 → 分
                },
                pay_type=WeChatPayType.NATIVE
            )

            if code != 200:
                logger.error(f"订单={order.order_no}[微信] 下单失败 code={code}, message={message}")
                raise ServiceWarning("微信支付下单失败")

            result = json.loads(message)

            pay_url = result.get("code_url")

            logger.info(f"[微信] 支付链接生成成功 order_no={order.order_no}")

            return pay_url