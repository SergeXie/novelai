import datetime
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from common.utils.generator import LZSDGenerator
from common.exception.lzsd_exception import ServiceWarning
from common.utils.time_format_util import parse_and_format_date
from core.entity.do.order_do import Order
from core.entity.do.users_do import User
from core.entity.vo.order_schema_vo import (
    CreateInternalOrderResponse,
    CreateOrderResponse,
    OrderListItem,
    UserOrderListItem,
)
from dao.order_dao import OrderDAO
from dao.product_dao import ProductDAO
from service.account_service import AccountService
from service.payment.payment_service import PaymentService


class OrderService:
    """
    订单服务层。
    """

    ORDER_EXPIRE_MINUTES = 30  # 订单过期时间，单位：分钟

    @staticmethod
    async def _build_product_snapshot(
        db: AsyncSession,
        order_type: str,
        target_code: str,
    ) -> tuple[float, str, dict]:
        if order_type == "MEMBERSHIP":
            product = await ProductDAO.get_membership_by_code(db, target_code)
            if not product or product.status != 1:
                raise ServiceWarning("Membership product is unavailable")

            amount = float(product.price)
            snapshot = {
                "price": amount,
                "duration_days": product.duration_days,
                "monthly_token": product.monthly_token_allowance,
                "models": product.unlocked_models,
            }
            return amount, product.level_name, snapshot

        if order_type == "TOKEN_PACKAGE":
            product = await ProductDAO.get_package_by_code(db, target_code)
            if not product or product.status != 1:
                raise ServiceWarning("Token package is unavailable")

            amount = float(product.price)
            snapshot = {
                "token_amount": product.token_amount,
                "expire_days": product.expire_days,
            }
            return amount, product.package_name, snapshot

        raise ServiceWarning("Invalid order type")

    @staticmethod
    async def cancel_expired_pending_orders(
            db: AsyncSession,
            user_id: int | None = None,
    ) -> int:
        """
        Cancel PENDING orders that have exceeded the configured payment window.
        """
        expired_before = datetime.datetime.utcnow() - datetime.timedelta(
            minutes=OrderService.ORDER_EXPIRE_MINUTES
        )

        count = await OrderDAO.cancel_expired_pending_orders(
            db=db,
            expired_before=expired_before,
            user_id=user_id,
        )

        if count:
            logger.info(f"[订单过期] 已关闭过期待支付订单 count={count}, user_id={user_id}")

        return count

    @staticmethod
    async def get_order_list(
            db,
            user_id: int,
            page: int,
            page_size: int,
            start_time: str | None = None,
            end_time: str | None = None
    ):
        """
        获取订单列表，支持时间筛选。
        """

        await OrderService.cancel_expired_pending_orders(db, user_id=user_id)

        records, total = await OrderDAO.list_orders(
            db,
            user_id=user_id,
            page=page,
            page_size=page_size,
            start_time=start_time,
            end_time=end_time
        )

        result = []

        for item in records:
            result.append(
                OrderListItem(
                    order_no=item.order_no,
                    order_type=item.order_type,
                    name=item.snapshot_name,
                    total_amount=item.total_amount,
                    pay_amount=item.pay_amount,
                    status=item.status,
                    paid_at=parse_and_format_date(item.paid_at),
                    pay_method=item.pay_method,
                    created_at=item.created_at,
                )
            )

        return result, total

    @staticmethod
    async def get_user_orders_with_product(
            db: AsyncSession,
            user_id: int,
            page: int,
            page_size: int,
    ) -> tuple[list[UserOrderListItem], int]:
        """内部查询指定用户的订单，并返回下单时的产品快照。"""
        await OrderService.cancel_expired_pending_orders(db, user_id=user_id)

        records, total = await OrderDAO.list_orders(
            db=db,
            user_id=user_id,
            page=page,
            page_size=page_size,
        )

        result = [
            UserOrderListItem(
                order_no=item.order_no,
                user_id=item.user_id,
                order_type=item.order_type,
                target_code=item.target_code,
                product_name=item.snapshot_name,
                product_snapshot=item.snapshot_content or {},
                total_amount=item.total_amount,
                pay_amount=item.pay_amount,
                status=item.status,
                pay_method=item.pay_method,
                paid_at=parse_and_format_date(item.paid_at),
                created_at=item.created_at,
            )
            for item in records
        ]
        return result, total

    @staticmethod
    async def query_order_status(db, order_no: str):
        """
        查询订单状态，带过期兜底。
        """

        order = await OrderDAO.get_by_order_no(db, order_no)

        if not order:
            return None

        if order.status == "PENDING":
            expire_time = order.created_at + datetime.timedelta(
                minutes=OrderService.ORDER_EXPIRE_MINUTES
            )
            if datetime.datetime.utcnow() >= expire_time:
                await OrderDAO.update_order_status(db, order, "CANCELLED")
                order.status = "CANCELLED"

        # 已支付订单直接返回成功状态

        if order.status == "PAID":
            return {
                "status": "PAID",
                "paid": True
            }

        # 后续可以在这里增加第三方主动查询。

        # if order.pay_method == "wechat":
        #     调用微信 query API
        # if order.pay_method == "alipay":
        #     调用支付宝 query API

        return {
            "status": order.status,
            "paid": False
        }

    @staticmethod
    async def create_order(
        db: AsyncSession,
        user_id: int,
        order_type: str,
        target_code: str,
        pay_method: str,
        return_url: str,
    ) -> CreateOrderResponse:
        """
        创建普通支付订单，带防重复和过期机制。

        流程：
        1. 校验支付方式
        2. 查询是否存在未支付订单
        3. 判断订单是否过期
        4. 校验商品
        5. 创建新订单
        """

        logger.info(f"[下单] 开始创建订单 user_id={user_id}, type={order_type}, code={target_code}")


        # 1. 校验支付方式
        if pay_method not in ("alipay", "wechat"):
            raise ServiceWarning("不支持的支付方式")

        # 2. 查询未支付订单
        pending_order = await OrderDAO.get_pending_order(
            db, user_id, order_type, target_code, pay_method
        )

        now = datetime.datetime.utcnow()

        # 3. 判断是否过期
        if pending_order:
            expire_time = pending_order.created_at + datetime.timedelta(
                minutes=OrderService.ORDER_EXPIRE_MINUTES
            )

            if now < expire_time:
                return_url = return_url + "&order_no={}".format(pending_order.order_no) +"&code=200"
                logger.info(f"[下单] 命中未过期订单 order_no={pending_order.order_no}")

                # 重新生成支付链接。
                payment_service = PaymentService()
                pay_url = await payment_service.generate_pay_url(pending_order, return_url)

                # 未过期，直接返回旧订单，避免重复下单。
                return CreateOrderResponse(
                    order_no=pending_order.order_no,
                    pay_method=pending_order.pay_method,
                    amount=float(pending_order.pay_amount),
                    pay_url=pay_url,
                    return_url=return_url
                )
            else:
                logger.info(f"[下单] 订单过期关闭 order_no={pending_order.order_no}")

                # 已过期，关闭订单。
                await OrderDAO.update_order_status(
                    db, pending_order, "CANCELLED"
                )

        # 4. 校验商品
        if order_type == "MEMBERSHIP":
            product = await ProductDAO.get_membership_by_code(db, target_code)
            if not product or product.status != 1:
                raise ServiceWarning("Membership product is unavailable")

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
                raise ServiceWarning("Token package is unavailable")

            amount = float(product.price)

            snapshot = {
                "token_amount": product.token_amount,
                "expire_days": product.expire_days
            }

            snapshot_name = product.package_name

        else:
            raise ServiceWarning("Invalid order type")

        # 5. 创建订单
        order_no = LZSDGenerator.generate_order_no()

        order = Order(
            order_no=order_no,
            user_id=user_id,
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

        # 生成支付链接
        return_url = return_url + "&order_no={}".format(order_no) + "&code=200"

        payment_service = PaymentService()
        pay_url = await payment_service.generate_pay_url(order, return_url)

        return CreateOrderResponse(
            order_no=order_no,
            pay_method=pay_method,
            amount=amount,
            pay_url=pay_url,
            return_url=return_url
        )

    @staticmethod
    async def create_internal_order(
        db: AsyncSession,
        user_id: int,
        order_type: str,
        target_code: str,
        operator_user_id: int,
        pay_amount: float = 0,
        remark: str | None = None,
    ) -> CreateInternalOrderResponse:
        """
        Create a paid internal order, then grant benefits through the normal order flow.
        """
        if pay_amount < 0:
            raise ServiceWarning("Internal order pay amount cannot be negative")

        if not await db.get(User, user_id):
            raise ServiceWarning("Target user does not exist")

        total_amount, snapshot_name, snapshot = await OrderService._build_product_snapshot(
            db=db,
            order_type=order_type,
            target_code=target_code,
        )
        snapshot["internal_order"] = True
        snapshot["operator_user_id"] = operator_user_id
        if remark:
            snapshot["remark"] = remark

        now = datetime.datetime.utcnow()
        order_no = LZSDGenerator.generate_order_no()
        order = Order(
            order_no=order_no,
            user_id=user_id,
            order_type=order_type,
            target_code=target_code,
            snapshot_name=snapshot_name,
            snapshot_content=snapshot,
            total_amount=total_amount,
            pay_amount=pay_amount,
            status="PAID",
            pay_method="internal",
            third_party_no=f"internal:{order_no}",
            paid_at=now,
        )

        await OrderDAO.create_order(db, order)
        await AccountService.grant_order_benefits(db, order)

        logger.info(
            f"[internal order] created and granted order_no={order_no}, user_id={user_id}, "
            f"operator={operator_user_id}, type={order_type}, code={target_code}, pay_amount={pay_amount}"
        )

        return CreateInternalOrderResponse(
            order_no=order.order_no,
            order_type=order.order_type,
            target_code=order.target_code,
            user_id=order.user_id,
            total_amount=float(order.total_amount),
            pay_amount=float(order.pay_amount),
            pay_method=order.pay_method,
            status=order.status,
            paid_at=parse_and_format_date(order.paid_at),
        )
