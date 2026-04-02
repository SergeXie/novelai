import json
from datetime import datetime

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from loguru import logger

from common.config.config import settings
from common.utils.time_format_util import parse_and_format_date
from dao.order_dao import OrderDAO
from service.account_service import AccountService
from service.payment.alipay_service import AlipayService
from service.payment.wechat_pay_service import WechatPayService


class PaymentService:
    """
    支付调度器（统一入口）

    职责：
    - 根据 pay_method 分发到不同支付实现
    - 不关心具体支付细节
    """

    def __init__(self):
        # 注册所有支付方式
        self.payment_map = {
            "alipay": AlipayService(),
            "wechat": WechatPayService(),
        }

    async def generate_pay_url(self, order) -> str:
        """
        统一生成支付链接入口

        :param order: 订单对象
        :return: pay_url
        """
        pay_method = order.pay_method

        logger.info(f"[支付调度] 开始处理支付 method={pay_method}, order_no={order.order_no}")

        if pay_method not in self.payment_map:
            logger.error(f"[支付调度] 不支持的支付方式 {pay_method}")
            raise ValueError("不支持的支付方式")

        service = self.payment_map[pay_method]

        pay_url = await service.generate_pay_url(order)

        logger.info(f"[支付调度] 支付链接生成完成 order_no={order.order_no}")

        return pay_url

    async def handle_alipay_callback(self, db, data: dict) -> bool:
        """
        支付宝回调处理（核心）

        :param db:
        :param data:
        :return:
        """

        logger.info("[回调] 开始处理支付宝回调")
        logger.info(f"sign字段: {data.get('sign')}")
        # ==================== 1. 验签 ====================
        signature = data.pop("sign", None)
        service = self.payment_map["alipay"]

        success = service.alipay.verify(data, signature)
        print("success:{}".format(success))
        if not success:
            logger.error("[回调] 验签失败")
            return False

        logger.info("[回调] 验签成功")

        # ==================== 2. 获取订单 ====================
        order_no = data.get("out_trade_no")
        trade_status = data.get("trade_status")
        gmt_payment = data.get("gmt_payment")  # 用户付款成功时间
        total_amount = data.get("total_amount")

        if trade_status not in ("TRADE_SUCCESS", "TRADE_FINISHED"):
            logger.warning(f"[回调] 非成功状态: {trade_status}")
            return False

        order = await OrderDAO.get_by_order_no(db, order_no)

        if not order:
            logger.error(f"[回调] 订单不存在 order_no={order_no}")
            return False

        # ==================== 3. 幂等控制 ====================
        if order.status == "PAID":
            logger.info(f"[回调] 订单已处理 order_no={order_no}")
            return True

        if float(total_amount) != float(order.pay_amount):
            logger.error(f"[回调] 金额不一致 order_no={order.order_no}")
            return False

        # ==================== 4. 更新订单 ====================
        order.status = "PAID"
        order.third_party_no = data.get("trade_no")

        if gmt_payment:
            order.paid_at = parse_and_format_date(gmt_payment)
        else:
            order.paid_at = parse_and_format_date()

        logger.info(f"[回调] 订单支付完成 order_no={order.order_no}, paid_at={order.paid_at}")
        # ==================== 5. 发放权益 ====================
        await AccountService.grant_order_benefits(db, order)

        logger.info(f"[回调] 权益发放完成 order_no={order_no}")

        return True

    def _decrypt_wechat(self, ciphertext, nonce, associated_data):
        """
        微信支付 AES-GCM 解密（正确版）
        """
        import base64
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        apiv3_key = settings.WECHATPAY_APIV3_KEY.encode()

        aesgcm = AESGCM(apiv3_key)

        decrypted = aesgcm.decrypt(
            nonce.encode(),
            base64.b64decode(ciphertext),  #  关键修复
            associated_data.encode() if associated_data else None
        )

        return json.loads(decrypted.decode())

    async def handle_wechat_callback(self, db, body: dict) -> bool:
        """
        微信支付回调处理
        """

        logger.info("[微信回调] 开始处理")

        try:
            # ==================== 1. 获取resource ====================

            resource = body.get("resource")
            if not resource:
                logger.error("resource为空")
                return False

            ciphertext = resource.get("ciphertext")
            nonce = resource.get("nonce")
            associated_data = resource.get("associated_data")

            # ==================== 2. 解密 ====================

            data = self._decrypt_wechat(
                ciphertext,
                nonce,
                associated_data
            )

            logger.info(f"[微信回调] 解密后数据: {data}")

            # ==================== 3. 校验状态 ====================

            if data.get("trade_state") != "SUCCESS":
                logger.warning(f"[微信回调] 非成功状态: {data.get('trade_state')}")
                return False

            order_no = data.get("out_trade_no")

            # ==================== 4. 查询订单 ====================

            order = await OrderDAO.get_by_order_no(db, order_no)

            if not order:
                logger.error(f"[微信回调] 订单不存在: {order_no}")
                return False

            # ==================== 5. 幂等 ====================

            if order.status == "PAID":
                logger.info(f"[微信回调] 已处理: {order_no}")
                return True

            # ==================== 6. 金额校验 ====================

            total = data.get("amount", {}).get("total")  # 分
            if int(total) != int(order.pay_amount * 100):
                logger.error("[微信回调] 金额不一致")
                return False

            # ==================== 7. 更新订单 ====================

            order.status = "PAID"
            order.third_party_no = data.get("transaction_id")

            # 时间
            success_time = data.get("success_time")
            if success_time:
                order.paid_at = datetime.fromisoformat(success_time.replace("Z", "+00:00"))

            logger.info(f"[微信回调] 订单支付成功: {order_no}")

            # ==================== 8. 发放权益 ====================

            await AccountService.grant_order_benefits(db, order)

            logger.info(f"[微信回调] 权益发放完成: {order_no}")

            return True

        except Exception as e:
            logger.error(f"[微信回调] 处理异常: {e}")
            return False
