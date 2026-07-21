from datetime import datetime
from typing import Optional, Dict

from sqlalchemy import (
    String, Text, DateTime, BigInteger, Integer, JSON
)
from sqlalchemy.orm import mapped_column, Mapped
from database.db_mysql import Base


class BookNode(Base):
    __tablename__ = "mc_book_node_copy2"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bid: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    uid: Mapped[int] = mapped_column(BigInteger,nullable=False,comment="用户ID")

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # 新增字段：type (tinyint)
    type: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="节点类型: 0目录, 1设定, 2人物, 3大纲"
    )

    # 内容字段：虽然数据库是 MEDIUMTEXT，Text 映射在 Python 中是最兼容的
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="核心内容")

    # 新增字段：data (JSON)
    # SQLAlchemy 会自动将 MySQL 的 JSON 映射为 Python 的 dict
    data: Mapped[Optional[Dict[str, str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="扩展配置数据"
    )

    depth: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="深度"
    )
    is_leaf: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="节点类型：0父节点 1子节点"
    )
    book_len: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="长度"
    )
    order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="排序"
    )
    parent_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)
    createTime: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updateTime: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)