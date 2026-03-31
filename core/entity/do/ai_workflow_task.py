from sqlalchemy import (
    BigInteger,
    String,
    Text,
    DateTime,
    Integer,
    SmallInteger,
    JSON,
    func,
    Index,
)
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from database.db_mysql import Base


class AiWorkflowTask(Base):
    __tablename__ = "ai_workflow_task"
    __table_args__ = (
        Index("uk_workflow_id", "workflowId", unique=True),
        Index("idx_user_status", "userId", "status"),
        {
            "comment": "AI多步工作流主任务表",
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
        },
    )

    id: Mapped[int] = mapped_column(
        BigInteger(unsigned=True),
        primary_key=True,
        autoincrement=True,
        comment="主键ID",
    )

    workflowId: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="工作流唯一ID(给前端查询用)",
    )

    userId: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="用户ID",
    )

    workflowType: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="工作流类型：outline_to_content / refine_polish",
    )

    totalSteps: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
        comment="总步骤数",
    )

    inputParams: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="初始全局输入参数",
    )

    finalOutput: Mapped[str | None] = mapped_column(
        LONGTEXT,
        nullable=True,
        comment="工作流最终产出结果",
    )

    status: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        server_default="0",
        comment="状态：0处理中 1全部完成 2部分失败 3已取消",
    )

    errorMsg: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="中断错误信息",
    )

    createdAt: Mapped[DateTime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        comment="创建时间",
    )

    updatedAt: Mapped[DateTime | None] = mapped_column(
        DateTime,
        nullable=True,
        onupdate=func.current_timestamp(),
        comment="更新时间",
    )
