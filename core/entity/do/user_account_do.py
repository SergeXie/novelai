from datetime import datetime
from typing import Optional, Dict
from sqlalchemy import String, Integer, DateTime, BigInteger, JSON
from sqlalchemy.orm import Mapped, mapped_column
from database.db_mysql import Base


class UserAccount(Base):
    """
    用户资产账户表

    👉 作用：
    - 管理用户会员状态
    - 管理 Token 余额（核心）
    - 控制并发扣费（乐观锁）
    """

    __tablename__ = "mc_user_accounts"

    # ==================== 主键 ====================

    uid: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        comment="用户ID（关联用户中心）"
    )

    # ==================== 会员信息 ====================

    level_code: Mapped[str] = mapped_column(
        String(32),
        default="basic",
        nullable=False,
        comment="当前会员等级 basic/pro_monthly/pro_annual/enterprise"
    )

    expire_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="会员到期时间"
    )

    # ==================== Token资产 ====================

    monthly_balance: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="月度Token余额（会员赠送，每月重置）"
    )

    permanent_balance: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="永久Token余额（充值获得）"
    )

    # ==================== 统计 ====================

    total_consumed: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
        comment="累计消耗Token总量"
    )

    last_reset_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="上一次月度额度重置时间"
    )

    # ==================== 并发控制（非常重要） ====================

    version: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="乐观锁版本号（防止并发扣费冲突）"
    )

    # ==================== 更新时间 ====================

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment="更新时间"
    )


class AccountLog(Base):
    """
    用户资产流水表（统一账本）
    """

    __tablename__ = "mc_account_logs"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="流水ID"
    )

    uid: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="用户ID"
    )

    # ==================== 业务关联 ====================

    biz_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="业务ID（订单号 / 请求ID）"
    )

    biz_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="业务类型 ORDER / AI_CONSUME / REFUND / SYSTEM"
    )

    # ==================== 变动 ====================

    change_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="RECHARGE / CONSUME / REFUND / EXPIRE / ADJUST"
    )

    asset_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="MONTHLY / PERMANENT"
    )

    amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="变动值（正数=增加，负数=减少）"
    )

    balance_after: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="变动后余额"
    )

    # ==================== 扩展信息 ====================

    extra: Mapped[Optional[Dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="扩展信息（模型、prompt、备注等）"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
        comment="创建时间"
    )