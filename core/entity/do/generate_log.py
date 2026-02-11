from sqlalchemy import (
    String, Text, DateTime, BigInteger, Integer, DECIMAL
)
from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy.sql import func
from database.db_mysql import Base


class AiNovelGenerateLog(Base):
    __tablename__ = "ai_novel_generate_log"
    __table_args__ = {
        "comment": "AI小说生成输入输出流水表"
    }

    # ========= 主键 =========
    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="主键ID"
    )

    # ========= 用户 =========
    userId: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
        comment="当前登录用户ID"
    )

    # ========= 输入(Input) =========
    userPrompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="用户输入的提示词"
    )

    systemPrompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="系统拼装后的提示词"
    )

    model: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="使用的模型名称"
    )

    temperature: Mapped[float] = mapped_column(
        DECIMAL(3, 2),
        nullable=False,
        comment="生成温度参数"
    )

    maxTokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="最大生成token数"
    )

    # ========= 输出(Output) =========
    outputContent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="模型生成的内容全文"
    )

    outputLength: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="生成内容字符数"
    )

    tokenEstimate: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="token估算值"
    )

    # ========= 执行状态 =========
    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="执行状态：1成功 0失败"
    )

    errorMsg: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="失败错误信息"
    )

    # ========= 时间 =========
    createdAt: Mapped[str] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="创建时间"
    )
