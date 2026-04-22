from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import and_

from core.entity.do.order_do import Order
from dao.base import BaseDAO


class OrderDAO(BaseDAO[Order]):
    """
    订单DAO层
    """

    @staticmethod
    async def list_orders(
            db: AsyncSession,
            user_id: int,
            page: int = 1,
            page_size: int = 10,
            start_time: str | None = None,
            end_time: str | None = None
    ):
        """
        查询订单列表（分页 + 时间筛选）
        """

        # ==================== 条件 ====================
        condition = [Order.user_id == user_id]

        #  时间筛选
        if start_time:
            condition.append(Order.created_at >= start_time)

        if end_time:
            condition.append(Order.created_at <= end_time)

        # ==================== 查询数据 ====================

        stmt = (
            select(Order)
            .where(and_(*condition))
            .order_by(desc(Order.paid_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await db.execute(stmt)
        records = result.scalars().all()

        # ==================== 查询总数 ====================

        count_stmt = select(func.count()).where(and_(*condition))
        total = (await db.execute(count_stmt)).scalar()

        return records, total

    @staticmethod
    async def get_pending_order(
        db: AsyncSession,
        user_id: int,
        order_type: str,
        target_code: str,
        pay_method:str
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
                Order.user_id == user_id,
                Order.order_type == order_type,
                Order.target_code == target_code,
                Order.pay_method == pay_method,
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