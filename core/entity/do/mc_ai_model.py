from sqlalchemy import (
    Integer,
    String,
    DateTime,
    DECIMAL,
    SmallInteger,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from database.db_mysql import Base


class McAiModel(Base):
    """
    AI 模型表 ORM
    """

    __tablename__ = "mc_ai_models"
    __table_args__ = (
        Index("idx_level_status", "level", "status"),
        {"comment": "AI模型表"},
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="自增主键",
    )

    level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        unique=True,
        comment="模型等级：1-基础, 2-进阶, 3-旗舰",
    )

    model_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="显示名称",
    )

    model_identifier: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="实际调用模型ID",
    )

    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="供应商",
    )

    multiplier: Mapped[float] = mapped_column(
        DECIMAL(10, 2),
        nullable=False,
        server_default="1.00",
        comment="计费倍率",
    )

    status: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        server_default="1",
        comment="状态：1-启用, 0-下架",
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