from loguru import logger
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

    def generate_pay_url(self, order) -> str:
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

        pay_url = service.generate_pay_url(order)

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

        # ==================== 1. 验签 ====================
        signature = data.pop("sign", None)

        service = self.payment_map["alipay"]

        success = service.alipay.verify(data, signature)

        if not success:
            logger.error("[回调] 验签失败")
            return False

        logger.info("[回调] 验签成功")

        # ==================== 2. 获取订单 ====================
        order_no = data.get("out_trade_no")
        trade_status = data.get("trade_status")

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

        # ==================== 4. 更新订单 ====================
        order.status = "PAID"
        order.third_party_no = data.get("trade_no")

        logger.info(f"[回调] 订单更新为已支付 order_no={order_no}")

        # ==================== 5. 发放权益 ====================
        await AccountService.grant_order_benefits(db, order)

        logger.info(f"[回调] 权益发放完成 order_no={order_no}")

        return True
