import datetime

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from database.db_mysql import Base


class AiNovelGenerateLogContent(Base):
    """AI 生成日志的大文本内容，与主日志一对一关联。"""

    __tablename__ = "ai_novel_generate_log_content"
    __table_args__ = {
        "comment": "AI小说生成日志大文本内容表",
    }

    log_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="关联 ai_novel_generate_log.id",
    )
    request_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="请求ID",
    )
    user_prompt: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="最终发送给模型的用户提示词",
    )
    system_prompt: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="系统提示词",
    )
    output_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="模型输出内容",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
