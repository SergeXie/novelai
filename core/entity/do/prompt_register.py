from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Integer, String, Text, JSON, DateTime, TIMESTAMP, func, text
from sqlalchemy.orm import Mapped, mapped_column
from database.db_mysql import Base


class PromptRegistry(Base):
    __tablename__ = "mc_prompt_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 工具标识，建立唯一索引
    tool_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, comment="工具唯一标识")

    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="工具名称")

    # 提示词模板，Text 类型足以存储长文本
    template_content: Mapped[str] = mapped_column(Text, nullable=False, comment="提示词原型")

    # 变量约束，MySQL 5.7 JSON 字段映射为 Python dict
    variables_schema: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="变量约束（字段名、类型等）"
    )

    # 渲染引擎
    engine_type: Mapped[str] = mapped_column(
        String(20),
        server_default="jinja2",
        default="jinja2",
        comment="渲染引擎"
    )

    # 状态
    status: Mapped[int] = mapped_column(
        Integer,
        server_default="1",
        default=1,
        comment="1:启用, 0:禁用"
    )

    # 时间字段优化
    # update_time 使用 TIMESTAMP 配合 MySQL 的自动更新机制
    update_time: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        comment="最后更新时间"
    )

    create_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        comment="创建时间"
    )

    isRelated: Mapped[int] = mapped_column(
        Integer,
        server_default="1",
        default=1,
        comment="1:关联, 0:不关联"
    )

    def __repr__(self) -> str:
        return f"<PromptRegistry(key='{self.tool_key}', name='{self.name}')>"