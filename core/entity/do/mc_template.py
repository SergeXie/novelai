from sqlalchemy import (
    Integer,
    String,
    JSON,
    SmallInteger,
    DateTime,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from database.db_mysql import Base


class McTemplate(Base):
    """
    节点树模板表
    """

    __tablename__ = "mc_templates"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="自增主键",
    )

    template_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        comment="模板唯一标识",
    )

    tpl_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="模板展示名称",
    )

    data: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="预设节点树结构",
    )

    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="模板描述",
    )

    status: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        server_default="1",
        comment="状态：1-启用, 0-禁用",
    )

    color: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="颜色",
    )

    createTime: Mapped[DateTime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )