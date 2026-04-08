from typing import Optional, Union, List, Dict, Any

from sqlalchemy import (
    String, Text, DateTime, BigInteger, Integer, DECIMAL, JSON
)
from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy.sql import func
from sqlalchemy import Enum as SqlEnum

from core.enums.token_consume_source import TokenConsumeSource
from database.db_mysql import Base


class AiNovelGenerateLog(Base):
    __tablename__ = "ai_novel_generate_log"
    __table_args__ = {
        "comment": "AI小说生成输入输出流水表",
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

    # ========= 作品id =========
    bid: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="所属小说ID"
    )

    # ========= 请求id =========
    requestId: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="请求id"
    )

    originPrompt: Mapped[str] = mapped_column(Text, nullable=False)

    # 存储节点 ID 数组，例如 ["node_1", "node_2"]
    # Mapped[Optional[list]] 对应 Python 的列表类型
    node_ids: Mapped[Optional[Union[List[Any], Dict[str, Any]]]] = mapped_column(
        JSON,
        nullable=True,
        comment="关联的节点ID数组"
    )

    # ========= 输入(Input) =========
    userPrompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="用户输入的提示词"
    )

    requestInputLength: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="生成请求输入总字符数"
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

    multiplier: Mapped[float] = mapped_column(
        DECIMAL(10, 2),
        nullable=False,
        server_default="1.00",
        comment="计费倍率",
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

    actionType: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="generate",
        comment="行为类型：generate / refine / render"
    )

    isDelete: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="逻辑删除 1 删除 0未删除"
    )

    # ========= 计费统计 =========

    totalTokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="模型返回的总Token数(Input+Output)"
    )

    actualAmount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="最终核减的计费Token数"
    )

    # 在模型类中
    consume_source: Mapped[TokenConsumeSource] = mapped_column(
        "consumeSource",  # 必须显式指定数据库里的原始列名（驼峰）
        SqlEnum(
            TokenConsumeSource,
            # 核心：告诉 SQLAlchemy 存取时使用 .value (即 "free")
            values_callable=lambda x: [item.value for item in x],
            native_enum=False
        ),
        nullable=False,
        default=TokenConsumeSource.FREE,
        server_default="free"
    )

    # ========= 资产拆解统计 =========
    freeDeduct: Mapped[int] = mapped_column(
        Integer, default=0, comment="本次消耗的每日免费额度"
    )

    monthlyDeduct: Mapped[int] = mapped_column(
        Integer, default=0, comment="本次消耗的会员月度额度"
    )

    permanentDeduct: Mapped[int] = mapped_column(
        Integer, default=0, comment="本次消耗的永久充值额度"
    )

    # ========= 时间 =========
    createdAt: Mapped[str] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="创建时间"
    )
