from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Integer, BigInteger, JSON, DateTime, UniqueConstraint, func
from datetime import datetime

from core.enums.prompt_sys_var import PromptEngineType
from database.db_mysql import Base


class PromptSquare(Base):
    """
    提示词广场模板表（ai_prompt_square）
    """

    __tablename__ = "ai_prompt_square"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="主键ID"
    )

    template_key: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        comment="唯一标识符（如:outline_generator）"
    )

    title: Mapped[str] = mapped_column(
        String(100),
        default="",
        comment="模板标题"
    )

    description: Mapped[str] = mapped_column(
        String(255),
        default="",
        comment="模板描述/简介"
    )

    freeze_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="预冻结token数量"
    )

    cover_img: Mapped[str] = mapped_column(
        String(255),
        default="",
        comment="封面图URL"
    )

    category: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="分类：大纲/正文/润色/设定"
    )

    tags: Mapped[list] = mapped_column(
        JSON,
        nullable=True,
        comment="标签数组，如：[小白可用, 玄幻]"
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="提示词模板内容（支持Jinja2/fstring）"
    )

    engine_type: Mapped[str] = mapped_column(
        String(16),
        default=PromptEngineType.JINJA2.value,
        comment="渲染引擎类型"
    )

    input_schema: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="输入参数结构（用于前端动态表单）"
    )

    author_id: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        comment="作者ID（0=官方）"
    )

    use_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="使用/收藏次数"
    )

    status: Mapped[int] = mapped_column(
        Integer,
        default=1,
        comment="状态：1=上架 0=下架"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        comment="创建时间"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间"
    )

class UserTemplateFavor(Base):
    """
    用户模板收藏表（mc_user_template_favor）
    """

    __tablename__ = "mc_user_template_favor"

    __table_args__ = (
        UniqueConstraint("user_id", "template_key", name="uk_user_tpl"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="主键ID"
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
        comment="用户ID"
    )

    template_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="关联 ai_prompt_square 的 template_key"
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="收藏时间"
    )

    prompt = relationship(
        "PromptSquare",
        primaryjoin="UserTemplateFavor.template_key == foreign(PromptSquare.template_key)",
        uselist=False,  # 关键
        lazy="joined"
    )