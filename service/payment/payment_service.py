import base64
import json
from datetime import datetime
from urllib.parse import parse_qsl

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from loguru import logger

from common.config.config import settings
from common.utils.time_format_util import parse_and_format_date
from dao.order_dao import OrderDAO
from service.account_service import AccountService
from service.payment.alipay_service import AlipayService
from service.payment.wechat_pay_service import WechatPayService


class PaymentService:
    """Payment dispatcher."""

    def __init__(self):
        self.payment_map = {
            "alipay": AlipayService(),
            "wechat": WechatPayService(),
        }

    async def generate_pay_url(self, order, return_url: str) -> str:
        pay_method = order.pay_method
        logger.info(f"[支付调度] 开始处理支付 method={pay_method}, order_no={order.order_no}")

        if pay_method not in self.payment_map:
            logger.error(f"[支付调度] 不支持的支付方式 {pay_method}")
            raise ValueError("不支持的支付方式")

        pay_url = await self.payment_map[pay_method].generate_pay_url(order, return_url)
        logger.info(f"[支付调度] 支付链接生成完成 order_no={order.order_no}")
        return pay_url

    @staticmethod
    def _normalize_alipay_data(data) -> dict:
        if isinstance(data, dict):
            return dict(data)
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        if isinstance(data, str):
            return dict(parse_qsl(data, keep_blank_values=True))
        return {}

    async def handle_alipay_callback(self, db, data) -> bool:
        data = self._normalize_alipay_data(data)
        if not data:
            logger.error("[回调] 支付宝回调参数为空或格式错误")
            return False

        logger.info("[回调] 开始处理支付宝回调")
        logger.info(f"sign字段: {data.get('sign')}")

        signature = data.pop("sign", None)
        service = self.payment_map["alipay"]

        success = service.alipay.verify(data, signature)
        if not success:
            logger.error("[回调] 支付宝验签失败")
            return False

        logger.info("[回调] 支付宝验签成功")

        order_no = data.get("out_trade_no")
        trade_status = data.get("trade_status")
        gmt_payment = data.get("gmt_payment")
        total_amount = data.get("total_amount")

        if trade_status not in ("TRADE_SUCCESS", "TRADE_FINISHED"):
            logger.warning(f"[回调] 非成功状态 {trade_status}")
            return False

        order = await OrderDAO.get_by_order_no(db, order_no)
        if not order:
            logger.error(f"[回调] 订单不存在 order_no={order_no}")
            return False

        if order.status == "PAID":
            logger.info(f"[回调] 订单已处理 order_no={order_no}")
            return True

        if float(total_amount) != float(order.pay_amount):
            logger.error(f"[回调] 金额不一致 order_no={order.order_no}")
            return False

        order.status = "PAID"
        order.third_party_no = data.get("trade_no")
        order.paid_at = parse_and_format_date(gmt_payment) if gmt_payment else parse_and_format_date()

        logger.info(f"[回调] 订单支付完成 order_no={order.order_no}, paid_at={order.paid_at}")
        await AccountService.grant_order_benefits(db, order)
        logger.info(f"[回调] 权益发放完成 order_no={order_no}")
        return True

    @staticmethod
    def _decrypt_wechat(ciphertext, nonce, associated_data):
        aesgcm = AESGCM(settings.WECHATPAY_APIV3_KEY.encode())
        decrypted = aesgcm.decrypt(
            nonce.encode(),
            base64.b64decode(ciphertext),
            associated_data.encode() if associated_data else None,
        )
        return json.loads(decrypted.decode())

    async def handle_wechat_callback(self, db, body: dict) -> bool:
        resource = body.get("resource")
        if not resource:
            logger.error("[微信回调] resource 为空")
            return False

        data = self._decrypt_wechat(
            ciphertext=resource.get("ciphertext"),
            nonce=resource.get("nonce"),
            associated_data=resource.get("associated_data"),
        )

        logger.info(f"[微信回调] 解密后数据: {data}")

        if data.get("trade_state") != "SUCCESS":
            logger.warning(f"[微信回调] 非成功状态 {data.get('trade_state')}")
            return False

        order_no = data.get("out_trade_no")
        order = await OrderDAO.get_by_order_no(db, order_no)
        if not order:
            logger.error(f"[微信回调] 订单不存在: {order_no}")
            return False

        if order.status == "PAID":
            logger.info(f"[微信回调] 已处理: {order_no}")
            return True

        total = data.get("amount", {}).get("total")
        if int(total) != int(order.pay_amount * 100):
            logger.error(f"[微信回调] 金额不一致 order_no={order_no}")
            return False

        order.status = "PAID"
        order.third_party_no = data.get("transaction_id")

        success_time = data.get("success_time")
        if success_time:
            order.paid_at = datetime.fromisoformat(success_time.replace("Z", "+00:00"))

        logger.info(f"[微信回调] 订单支付成功: {order_no}")
        await AccountService.grant_order_benefits(db, order)
        logger.info(f"[微信回调] 权益发放完成: {order_no}")
        return True
