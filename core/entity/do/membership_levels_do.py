from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, Enum, DECIMAL, JSON, TIMESTAMP
from sqlalchemy.sql import func

from database.db_mysql import Base


class MembershipLevel(Base):
    """
    会员等级配置表（静态配置表）

    用于定义：
    - 会员价格
    - 有效期
    - 每月发放Token
    - 解锁模型
    - 额外权益

    注意：这是“商品表”，不是用户实际拥有的会员
    """

    __tablename__ = "mc_membership_levels"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 会员编码（唯一标识，业务侧使用）
    level_code: Mapped[str] = mapped_column(
        Enum('basic', 'pro_monthly', 'pro_annual', 'enterprise'),
        nullable=False,
        comment="会员唯一编码"
    )

    # 前端展示名称
    level_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="展示名称"
    )

    # 描述说明
    description: Mapped[str] = mapped_column(
        String(255),
        default="",
        comment="会员描述"
    )

    # 所属梯队（用于区分基础/专业/企业）
    tier_type: Mapped[str] = mapped_column(
        Enum('basic', 'pro', 'enterprise'),
        default='basic',
        comment="会员梯队"
    )

    # 权重（用于排序/升级逻辑）
    rank_weight: Mapped[int] = mapped_column(
        default=1,
        comment="等级权重（越大等级越高）"
    )

    # 售价
    price: Mapped[float] = mapped_column(
        DECIMAL(10, 2),
        default=0.00,
        comment="价格"
    )

    # 有效期（天）
    duration_days: Mapped[int] = mapped_column(
        default=30,
        comment="会员有效期（天）"
    )

    # 每月发放Token数量
    monthly_token_allowance: Mapped[int] = mapped_column(
        default=0,
        comment="每月赠送Token"
    )

    # 解锁模型（JSON数组）
    unlocked_models: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="解锁模型列表"
    )

    # 扩展权益（JSON）
    extra_privileges: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="额外权益（并发数/优先级等）"
    )

    # 是否在售（1=在售）
    status: Mapped[int] = mapped_column(
        default=1,
        comment="是否在售"
    )

    # 创建时间
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP,
        server_default=func.now()
    )