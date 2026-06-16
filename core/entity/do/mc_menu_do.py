from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from database.db_mysql import Base


class McMenu(Base):
    """系统多模块通用分类配置表。"""

    __tablename__ = "mc_menu"
    __table_args__ = (
        UniqueConstraint("module_key", "key", name="uk_module_category"),
        Index("idx_module_status_sort", "module_key", "status", "weight"),
        {"comment": "系统多模块通用分类配置表"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键ID")
    module_key: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="所属业务模块标识(如: prompt_square, material_lib)",
    )
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="分类显示名称(如: 扩写)",
    )
    key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="分类英文唯一标识(前端路由/代码逻辑映射用, 如: expand)",
    )
    weight: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        server_default="0",
        comment="排序权重(数值越小越靠前)",
    )
    status: Mapped[int] = mapped_column(
        nullable=False,
        default=1,
        server_default="1",
        comment="上下架状态(1:显示/上架, 0:隐藏/下架)",
    )
    create_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        comment="创建时间",
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        comment="更新时间",
    )


class McModule(Base):
    """业务模块注册表。"""

    __tablename__ = "mc_module"
    __table_args__ = (
        UniqueConstraint("module_key", name="uk_module_key"),
        {"comment": "业务模块注册表"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    module_key: Mapped[str] = mapped_column(String(50), nullable=False, comment="模块唯一标识")
    module_name: Mapped[str] = mapped_column(String(64), nullable=False, comment="模块中文名称")
