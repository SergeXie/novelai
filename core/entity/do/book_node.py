from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String, Text, DateTime, BigInteger, Integer, DECIMAL
)
from sqlalchemy.orm import mapped_column, Mapped
from database.db_mysql import Base


class BookNode(Base):
    __tablename__ = "mc_book_node"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bid: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    uid: Mapped[int] = mapped_column(BigInteger,nullable=False,comment="用户ID")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text)  # 虽然表里是MEDIUMTEXT，模型用Text即可
    depth: Mapped[int] = mapped_column(Integer)
    is_leaf: Mapped[int] = mapped_column(Integer)
    parent_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)
    createTime: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updateTime: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)