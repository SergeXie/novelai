import uuid
import datetime

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from common.exception.lzsd_exception import ServiceWarning
from core.entity.do.order_do import Order
from core.entity.vo.order_schema_vo import CreateOrderResponse
from dao.order_dao import OrderDAO
from dao.product_dao import ProductDAO
from service.payment.payment_service import PaymentService


class OrderService:
    """
    订单服务层（核心业务逻辑）
    """

    ORDER_EXPIRE_MINUTES = 30  # 订单过期时间（分钟）

    @staticmethod
    async def create_order(
        db: AsyncSession,
        uid: str,
        order_type: str,
        target_code: str,
        pay_method: str
    ) -> CreateOrderResponse:
        """
        创建订单（带防重复 + 过期机制）

        流程：
        1. 校验支付方式
        2. 查是否已有未支付订单
        3. 判断是否过期（30分钟）
        4. 校验商品
        5. 创建新订单
        """

        logger.info(f"[下单] 开始创建订单 uid={uid}, type={order_type}, code={target_code}")


        # ==================== 1. 校验支付方式 ====================
        if pay_method not in ("alipay", "wechat"):
            raise ServiceWarning("不支持的支付方式")

        # ==================== 2. 查未支付订单 ====================
        pending_order = await OrderDAO.get_pending_order(
            db, uid, order_type, target_code
        )

        now = datetime.datetime.utcnow()

        # ==================== 3. 判断是否过期 ====================
        if pending_order:
            expire_time = pending_order.created_at + datetime.timedelta(
                minutes=OrderService.ORDER_EXPIRE_MINUTES
            )

            if now < expire_time:
                logger.info(f"[下单] 命中未过期订单 order_no={pending_order.order_no}")

                # 重新生成支付链接（关键点）
                payment_service = PaymentService()
                pay_url = payment_service.generate_pay_url(pending_order)

                # 未过期 → 直接返回旧订单（防重复）
                return CreateOrderResponse(
                    order_no=pending_order.order_no,
                    pay_method=pending_order.pay_method,
                    amount=float(pending_order.pay_amount),
                    pay_url=pay_url
                )
            else:
                logger.info(f"[下单] 订单过期关闭 order_no={pending_order.order_no}")

                # 已过期 → 关闭订单
                await OrderDAO.update_order_status(
                    db, pending_order, "CANCELLED"
                )

        # ==================== 4. 校验商品 ====================
        if order_type == "MEMBERSHIP":
            product = await ProductDAO.get_membership_by_code(db, target_code)
            if not product or product.status != 1:
                raise ServiceWarning("会员不存在或已下架")

            amount = float(product.price)

            snapshot = {
                "price": amount,
                "duration_days": product.duration_days,
                "monthly_token": product.monthly_token_allowance,
                "models": product.unlocked_models
            }

            snapshot_name = product.level_name

        elif order_type == "TOKEN_PACKAGE":
            product = await ProductDAO.get_package_by_code(db, target_code)
            if not product or product.status != 1:
                raise ServiceWarning("充值包不存在或已下架")

            amount = float(product.price)

            snapshot = {
                "token_amount": product.token_amount,
                "expire_days": product.expire_days
            }

            snapshot_name = product.package_name

        else:
            raise ServiceWarning("非法订单类型")

        # ==================== 5. 创建订单 ====================
        order_no = uuid.uuid4().hex

        order = Order(
            order_no=order_no,
            uid=uid,
            order_type=order_type,
            target_code=target_code,
            snapshot_name=snapshot_name,
            snapshot_content=snapshot,
            total_amount=amount,
            pay_amount=amount,
            status="PENDING",
            pay_method=pay_method
        )

        await OrderDAO.create_order(db, order)

        logger.info(f"[下单] 订单创建成功 order_no={order_no}")

        # ==================== 生成支付链接 ====================
        payment_service = PaymentService()
        pay_url = payment_service.generate_pay_url(order)

        return CreateOrderResponse(
            order_no=order_no,
            pay_method=pay_method,
            amount=amount,
            pay_url=pay_url
        )
