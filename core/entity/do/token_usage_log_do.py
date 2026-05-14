from datetime import datetime
from typing import Optional, Dict

from sqlalchemy import String, Integer, BigInteger, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from database.db_mysql import Base


class TokenUsageLog(Base):
    """
    Token资产流水表（财务级日志）

    👉 作用：
    - 记录所有 Token 变化
    - 支持审计 / 对账
    - 支持问题排查（非常重要）
    """

    __tablename__ = "mc_token_usage_logs"

    # ==================== 主键 ====================

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="流水ID"
    )

    # ==================== 用户 ====================

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        index=True,
        comment="用户ID"
    )

    # ==================== 业务关联 ====================

    request_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="关联请求ID（如生成任务ID / 订单ID）"
    )

    # ==================== 动作类型 ====================

    action_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="""
        动作类型：
        CONSUME = 消耗
        REFUND = 退款
        RECHARGE = 充值
        EXPIRE = 过期清零
        """
    )

    # ==================== Token变动 ====================

    monthly_amount: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="月度额度变动（负数=消耗，正数=增加）"
    )

    bonus_amount: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="补给奖励额度变动"
    )

    permanent_amount: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="永久额度变动"
    )

    total_amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="总变动（monthly + permanent）"
    )

    # ==================== 余额快照 ====================

    balance_snapshot: Mapped[Optional[Dict]] = mapped_column(
        JSON,
        nullable=True,
        comment='变动后余额快照 {"monthly": 500, "permanent": 1200}'
    )

    # ==================== 时间 ====================

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
        comment="创建时间"
    )
