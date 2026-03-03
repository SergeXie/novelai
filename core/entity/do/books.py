from sqlalchemy import (
    BigInteger,
    String,
    Text,
    DateTime,
    Integer,
    SmallInteger,
    func,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from database.db_mysql import Base


class Book(Base):
    __tablename__ = "books"
    __table_args__ = (
        Index("idxUid", "bid"),
        Index("idxStatus", "status"),
        {
            "comment": "书籍表",
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
        },
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="书籍ID",
    )

    uid: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="用户ID",
    )

    bid: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="作者/用户ID",
    )

    bookType: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="作品类型",
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="书名",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="书籍简介",
    )

    status: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        server_default="0",
        comment="状态：0草稿 1连载中 2已完结 3下架",
    )

    wordCount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="全书总字数",
    )

    createTime: Mapped[DateTime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        comment="创建时间",
    )

    updateTime: Mapped[DateTime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        comment="更新时间",
    )