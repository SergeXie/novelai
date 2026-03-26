from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Enum, DECIMAL, JSON, TIMESTAMP, DateTime
from sqlalchemy.sql import func

from database.db_mysql import Base


class Order(Base):
    """
    订单表（核心交易表）

    用途：
    - 记录用户每一次购买行为（会员 / Token包）
    - 作为支付系统的唯一凭证
    - 支付成功后，用于发放权益

    核心原则：
    - 订单一旦创建，核心字段不可随意修改（价格、商品信息）
    - 所有支付、退款、发放都围绕订单进行
    """

    __tablename__ = "mc_orders"

    # ==================== 基础信息 ====================

    # 系统唯一订单号（建议：UUID / 雪花ID）
    order_no: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        comment="订单号（全局唯一）"
    )

    # 用户ID
    uid: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="用户ID"
    )

    # 订单类型（会员 or Token包）
    order_type: Mapped[str] = mapped_column(
        Enum('MEMBERSHIP', 'TOKEN_PACKAGE'),
        nullable=False,
        comment="订单类型"
    )

    # 商品编码（level_code / package_code）
    target_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="商品编码"
    )

    # ==================== 商品快照 ====================

    # 商品名称快照（防止商品改名）
    snapshot_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="商品名称快照"
    )

    # 商品完整快照（价格 / Token / 权益等）
    snapshot_content: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="商品快照JSON"
    )

    # ==================== 金额 ====================

    # 原价（未优惠）
    total_amount: Mapped[float] = mapped_column(
        DECIMAL(10, 2),
        nullable=False,
        comment="订单原价"
    )

    # 实付金额（考虑优惠券/活动）
    pay_amount: Mapped[float] = mapped_column(
        DECIMAL(10, 2),
        nullable=False,
        comment="实际支付金额"
    )

    # ==================== 状态 ====================

    # 订单状态
    status: Mapped[str] = mapped_column(
        Enum('PENDING', 'PAID', 'CANCELLED', 'REFUNDED'),
        default='PENDING',
        comment="订单状态"
    )

    # 支付方式（alipay / wechat）
    pay_method: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="支付方式"
    )

    # 第三方支付流水号
    third_party_no: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="第三方交易号"
    )

    # 支付成功时间
    paid_at: Mapped[str | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="支付时间"
    )

    # ==================== 时间 ====================

    created_at: Mapped[str] = mapped_column(
        TIMESTAMP,
        server_default=func.now(),
        comment="创建时间"
    )

    updated_at: Mapped[str] = mapped_column(
        TIMESTAMP,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间"
    )