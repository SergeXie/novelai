from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import (
    BigInteger,
    String,
    Text,
    DateTime,
    Integer,
    SmallInteger,
    func,
    Index, JSON,
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

    template_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        comment="模板唯一标识",
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


class McBookAsset(Base):
    """
    拆书资产记录实体 (DO)
    """
    __tablename__ = "mc_book_assets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="用户ID")

    # 业务核心字段
    request_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="AI生成请求唯一标识")
    title: Mapped[str] = mapped_column(String(255), nullable=False, comment="书籍名称")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="内容指纹")

    # 扩展属性
    ext_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True, comment="扩展配置")
    status: Mapped[int] = mapped_column(SmallInteger, default=1, comment="状态：1正常 0禁用")
    is_delete: Mapped[int] = mapped_column(SmallInteger, default=0, comment="逻辑删除：1已删除 0未删除")

    # 时间审计（由数据库层自动处理，Python层设为只读/自动）
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间"
    )

    def __repr__(self) -> str:
        return f"<McBookAsset(id={self.id}, title='{self.title}', requestId='{self.request_id}')>"