from datetime import datetime

from sqlalchemy import (
    Integer,
    String,
    DateTime,
    Column, Boolean,
)

from database.db_mysql import Base


class AIChatGroupDO(Base):
    """对应 ai_chat_groups 表"""
    __tablename__ = 'ai_chat_groups'

    id = Column(Integer, primary_key=True, autoincrement=True)
    gid = Column(String(36), nullable=False, unique=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    weight = Column(Integer, default=0)
    is_pinned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)