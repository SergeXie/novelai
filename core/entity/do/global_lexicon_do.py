from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, JSON, String, func
from sqlalchemy.dialects.mysql import MEDIUMTEXT, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from database.db_mysql import Base


class McGlobalLexicon(Base):
    """公共词条库。"""

    __tablename__ = "mc_global_lexicon"
    __table_args__ = (
        Index("idx_uid_share", "user_id", "share_level"),
        Index("idx_title", "title"),
        {"comment": "公共词条库"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="创建者用户ID")
    title: Mapped[str] = mapped_column(String(100), nullable=False, comment="词条名称")
    lexicon_type: Mapped[int] = mapped_column(TINYINT, nullable=False, comment="1角色, 2世界观, 3功法, 4道具")
    content: Mapped[str | None] = mapped_column(MEDIUMTEXT, nullable=True, comment="详细设定描述")
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="别名、扩展属性")
    share_level: Mapped[int] = mapped_column(
        TINYINT,
        nullable=False,
        default=0,
        server_default="0",
        comment="共享等级: 0私有, 1系列可见, 2全平台公开",
    )
    create_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        comment="创建时间",
    )
