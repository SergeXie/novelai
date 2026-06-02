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
        logger.info(f"[payment] generate url method={pay_method}, order_no={order.order_no}")

        if pay_method not in self.payment_map:
            logger.error(f"[payment] unsupported pay method={pay_method}")
            raise ValueError("unsupported pay method")

        pay_url = await self.payment_map[pay_method].generate_pay_url(order, return_url)
        logger.info(f"[payment] url generated order_no={order.order_no}")
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
            logger.error("[alipay callback] empty or invalid payload")
            return False

        logger.info("[alipay callback] start")
        logger.info(f"[alipay callback] sign={data.get('sign')}")

        signature = data.get("sign")
        verify_data = {
            key: value
            for key, value in data.items()
            if key != "sign"
        }
        service = self.payment_map["alipay"]

        logger.info(
            f"[alipay callback] verify context app_id={data.get('app_id')}, "
            f"out_trade_no={data.get('out_trade_no')}, sign_type={data.get('sign_type')}, "
            f"keys={sorted(verify_data.keys())}"
        )

        success = service.alipay.verify(verify_data, signature)
        if not success:
            logger.error("[alipay callback] verify failed")
            return False

        logger.info("[alipay callback] verify success")

        order_no = data.get("out_trade_no")
        trade_status = data.get("trade_status")
        gmt_payment = data.get("gmt_payment")
        total_amount = data.get("total_amount")

        if trade_status not in ("TRADE_SUCCESS", "TRADE_FINISHED"):
            logger.warning(f"[alipay callback] non-success trade_status={trade_status}")
            return False

        order = await OrderDAO.get_by_order_no(db, order_no)
        if not order:
            logger.error(f"[alipay callback] order not found order_no={order_no}")
            return False

        if order.status == "PAID":
            logger.info(f"[alipay callback] order already handled order_no={order_no}")
            return True

        if float(total_amount) != float(order.pay_amount):
            logger.error(f"[alipay callback] amount mismatch order_no={order.order_no}")
            return False

        order.status = "PAID"
        order.third_party_no = data.get("trade_no")
        order.paid_at = parse_and_format_date(gmt_payment) if gmt_payment else parse_and_format_date()

        logger.info(f"[alipay callback] order paid order_no={order.order_no}, paid_at={order.paid_at}")
        await AccountService.grant_order_benefits(db, order)
        logger.info(f"[alipay callback] benefits granted order_no={order_no}")
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
            logger.error("[wechat callback] empty resource")
            return False

        data = self._decrypt_wechat(
            ciphertext=resource.get("ciphertext"),
            nonce=resource.get("nonce"),
            associated_data=resource.get("associated_data"),
        )

        logger.info(f"[wechat callback] decrypted data={data}")

        if data.get("trade_state") != "SUCCESS":
            logger.warning(f"[wechat callback] non-success trade_state={data.get('trade_state')}")
            return False

        order_no = data.get("out_trade_no")
        order = await OrderDAO.get_by_order_no(db, order_no)
        if not order:
            logger.error(f"[wechat callback] order not found order_no={order_no}")
            return False

        if order.status == "PAID":
            logger.info(f"[wechat callback] order already handled order_no={order_no}")
            return True

        total = data.get("amount", {}).get("total")
        if int(total) != int(order.pay_amount * 100):
            logger.error(f"[wechat callback] amount mismatch order_no={order_no}")
            return False

        order.status = "PAID"
        order.third_party_no = data.get("transaction_id")

        success_time = data.get("success_time")
        if success_time:
            order.paid_at = datetime.fromisoformat(success_time.replace("Z", "+00:00"))

        logger.info(f"[wechat callback] order paid order_no={order_no}")
        await AccountService.grant_order_benefits(db, order)
        logger.info(f"[wechat callback] benefits granted order_no={order_no}")
        return True
