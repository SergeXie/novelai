from datetime import datetime
from decimal import Decimal

from sqlalchemy import DECIMAL, DateTime, Index, Integer, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database.db_mysql import Base


class McAiModel(Base):
    """AI model config ORM."""

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
        comment="显示名称，如：豆包-Pro",
    )

    model_identifier: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="实际调用的模型ID，如：ep-2026-xxx",
    )

    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="供应商：doubao, deepseek, openai",
    )

    multiplier: Mapped[Decimal] = mapped_column(
        DECIMAL(10, 1),
        nullable=True,
        server_default="1.0",
        comment="计费倍率，默认1.0",
    )

    input_price: Mapped[Decimal] = mapped_column(
        DECIMAL(10, 2),
        nullable=False,
        server_default="0.00",
        comment="输入每100万Token的人民币成本价",
    )

    output_price: Mapped[Decimal] = mapped_column(
        DECIMAL(10, 2),
        nullable=False,
        server_default="0.00",
        comment="输出每100万Token的人民币成本价",
    )

    sale_multiplier: Mapped[Decimal] = mapped_column(
        DECIMAL(10, 2),
        nullable=False,
        server_default="5.00",
        comment="成本售价倍率",
    )

    max_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="4096",
        comment="该模型允许的最大生成Token数",
    )

    temperature: Mapped[Decimal] = mapped_column(
        DECIMAL(10, 1),
        nullable=False,
        server_default="0.7",
        comment="模型温度",
    )

    context_window: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="32768",
        comment="该模型支持的最大上下文窗口(输入+输出)",
    )

    base_url: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default="",
        comment="模型服务Base URL",
    )

    api_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default="",
        comment="模型服务API Key",
    )

    weight: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        comment="权重",
    )

    status: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=True,
        server_default="1",
        comment="状态：1-启用, 0-下架",
    )

    createTime: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        comment="创建时间",
    )

    updateTime: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        comment="自动更新时间",
    )
