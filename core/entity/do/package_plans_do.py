from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Enum, DECIMAL, TIMESTAMP
from sqlalchemy.sql import func
from database.db_mysql import Base


class PackagePlan(Base):
    """
    Token充值包配置表（静态商品表）

    用于定义：
    - Token数量
    - 价格
    - 是否过期
    - 类型（普通/促销/补偿）
    """
    __tablename__ = "mc_package_plans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 包唯一编码（用于下单）
    package_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="充值包编码"
    )

    # 展示名称
    package_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="充值包名称"
    )

    # 描述
    description: Mapped[str] = mapped_column(
        String(64),
        default="",
        comment="描述"
    )

    # 包类型（用于业务区分）
    package_type: Mapped[str] = mapped_column(
        Enum('standard', 'promotion', 'compensation'),
        default='standard',
        comment="充值包类型"
    )

    # Token数量
    token_amount: Mapped[int] = mapped_column(
        nullable=False,
        comment="包含Token数量"
    )

    # 售价
    price: Mapped[float] = mapped_column(
        DECIMAL(10, 2),
        nullable=False,
        comment="价格"
    )

    # 过期时间（0=永久）
    expire_days: Mapped[int] = mapped_column(
        default=0,
        comment="有效期（天）"
    )

    # 排序（越小越靠前）
    sort_order: Mapped[int] = mapped_column(
        default=0,
        comment="排序权重"
    )

    # 是否在售
    status: Mapped[int] = mapped_column(
        default=1,
        comment="是否在售"
    )

    created_at: Mapped[str] = mapped_column(
        TIMESTAMP,
        server_default=func.now()
    )

    updated_at: Mapped[str] = mapped_column(
        TIMESTAMP,
        server_default=func.now(),
        onupdate=func.now()
    )