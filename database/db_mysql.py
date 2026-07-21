from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase

from common.config.config import settings

async_engine = create_async_engine(
        url=settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,  # 连接获取前检测是否可用，防止失效连接
        pool_recycle=300,  # 60 分钟后回收连接，防止 MySQL 连接超时
        pool_size=20,  # 连接池最大连接数，适用于高并发
        max_overflow=10,  # 连接池最大溢出数，可创建额外连接数
        pool_timeout=30,  # 获取连接的超时时间，防止阻塞
)


AsyncSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=async_engine,
    expire_on_commit=False
)


class Base(AsyncAttrs, DeclarativeBase):
    pass
