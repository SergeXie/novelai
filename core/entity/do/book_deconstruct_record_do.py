import datetime

from sqlalchemy import (
    BigInteger,
    String,
    DateTime,
    Integer,
    func,
    Index
)
from sqlalchemy.orm import mapped_column, Mapped

from database.db_mysql import Base


class BookDeconstructRecord(Base):
    __tablename__ = "book_deconstruct_record"

    __table_args__ = (
        # 用户时间排序索引
        Index("idx_user_created", "userId", "createdAt"),

        {
            "comment": "拆书记录表",
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
        }
    )

    # =========================
    # 主键
    # =========================
    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="主键ID"
    )

    # =========================
    # 用户信息
    # =========================
    userId: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
        comment="用户ID"
    )

    # =========================
    # 任务信息
    # =========================
    requestId: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="AI任务请求ID"
    )

    bookHash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="书籍内容SHA256"
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="未命名作品",
        comment="书名"
    )

    sourceUrl: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="原始TXT链接"
    )


    # =========================
    # 逻辑删除
    # =========================
    isDelete: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="逻辑删除 0未删除 1已删除"
    )

    # =========================
    # 时间
    # =========================
    createdAt: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="创建时间"
    )

    updatedAt: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间"
    )