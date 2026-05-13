# models/pv_log.py

from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Text,
    DateTime
)

from datetime import datetime

from database.db_mysql import Base


class McPVLog(Base):
    """
    PV访问日志表
    """

    __tablename__ = "mc_pv_logs"

    # 主键ID
    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="主键ID"
    )

    # 访客ID
    # 可以是：
    # - 登录用户ID
    # - 游客UUID
    # - session_id
    visitor_id = Column(
        String(128),
        nullable=True,
        comment="访客ID"
    )

    # 页面路径
    page = Column(
        String(255),
        nullable=False,
        comment="页面路径"
    )

    # 浏览器名称
    browser = Column(
        String(100),
        nullable=True,
        comment="浏览器名称"
    )

    # IP地址
    ip = Column(
        String(45),
        nullable=True,
        comment="IP地址"
    )

    # 设备类型
    # 例如：
    # - desktop
    # - mobile
    # - tablet
    device = Column(
        String(100),
        nullable=True,
        comment="设备类型"
    )

    # 来源页面
    referer = Column(
        String(500),
        nullable=True,
        comment="来源页面"
    )

    # 完整User-Agent
    user_agent = Column(
        String(128),
        nullable=True,
        comment="完整UA信息"
    )

    sub = Column(
        String(100),
        nullable=True,
        comment="子分类/维度"
    )


    # 创建时间
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        comment="创建时间"
    )