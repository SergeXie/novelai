import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.entity.do.order_do import Order


class OrderDAO:
    """
    订单DAO层
    """

    @staticmethod
    async def get_pending_order(
        db: AsyncSession,
        uid: str,
        order_type: str,
        target_code: str
    ):
        """
        查询用户未支付订单（防重复用）

        条件：
        - 同一用户
        - 同一商品
        - 状态 = PENDING
        """
        stmt = (
            select(Order)
            .where(
                Order.uid == uid,
                Order.order_type == order_type,
                Order.target_code == target_code,
                Order.status == "PENDING"
            )
            .order_by(Order.created_at.desc())
        )

        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def create_order(db: AsyncSession, order: Order):
        """
        插入订单
        """
        db.add(order)
        await db.flush()  # 让SQL执行（不commit）
        return order

    @staticmethod
    async def update_order_status(
        db: AsyncSession,
        order: Order,
        status: str
    ):
        """
        更新订单状态（如：过期关闭）
        """
        order.status = status
        await db.flush()

    @staticmethod
    async def get_by_order_no(db: AsyncSession, order_no: str):
        stmt = select(Order).where(Order.order_no == order_no)
        result = await db.execute(stmt)
        return result.scalars().first()