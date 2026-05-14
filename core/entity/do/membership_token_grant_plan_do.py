from datetime import datetime
from typing import Optional, Dict

from sqlalchemy import BigInteger, DateTime, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.db_mysql import Base


class MembershipTokenGrantPlan(Base):
    """
    会员月度 Token 分期发放计划。
    """

    __tablename__ = "mc_membership_token_grant_plans"
    __table_args__ = (
        UniqueConstraint("order_no", "cycle_no", "period_no", name="uq_membership_token_grant_period"),
        {"comment": "会员月度Token分期发放计划表"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="计划ID")

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="用户ID")
    order_no: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="订单号")
    level_code: Mapped[str] = mapped_column(String(32), nullable=False, comment="会员等级")

    cycle_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="第几个月周期，从1开始")
    period_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="周期内期数，-1=清零，0=基础额度，1-4=周五补给")
    plan_type: Mapped[str] = mapped_column(String(16), nullable=False, default="BASE", comment="计划类型 BASE/BONUS/RESET")

    amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="本期发放Token数量")
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True, comment="计划执行时间")
    issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="实际执行时间")
    membership_expire_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="本订单会员到期时间")

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING", index=True, comment="PENDING/ISSUED/CANCELED/FAILED")

    extra: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True, comment="扩展信息")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, comment="更新时间")
