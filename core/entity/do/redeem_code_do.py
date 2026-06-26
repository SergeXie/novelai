from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database.db_mysql import Base


class RedeemCode(Base):
    __tablename__ = "mc_redeem_code"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, comment="唯一兑换码串")
    batch_id: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="批次号")
    token_amount: Mapped[int] = mapped_column(Integer, nullable=False, comment="该码可兑换的Token数量")
    valid_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30, server_default="30", comment="兑换后Token有效天数")
    remaining_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", comment="兑换后剩余Token数量")
    code_expired_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="兑换码本身截止使用日期")
    token_expired_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="兑换后Token额度到期时间")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", comment="0未使用 1已兑换 2已作废")
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="兑换人用户ID")
    redeem_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="具体兑换时间")
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    update_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
