from typing import TypeVar, Generic, Type, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

# 定义一个泛型变量 T，绑定到 SQLAlchemy 的模型类
T = TypeVar("T")

class BaseDAO(Generic[T]):
    def __init__(self, model: Type[T], db: AsyncSession):
        self.model = model
        self.db = db

    async def get_by_id(self, ident: Any) -> Optional[T]:
        """根据主键 ID 获取单条数据"""
        result = await self.db.execute(select(self.model).where(self.model.id == ident))
        return result.scalars().first()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """分页获取所有数据"""
        result = await self.db.execute(select(self.model).offset(skip).limit(limit))
        return result.scalars().all()

    async def create(self, **kwargs) -> T:
        """创建新数据项"""
        instance = self.model(**kwargs)
        self.db.add(instance)
        await self.db.flush()  # 刷新以获取数据库生成的 ID
        return instance

    async def delete_by_id(self, ident: Any) -> bool:
        """根据 ID 删除"""
        await self.db.execute(delete(self.model).where(self.model.id == ident))
        return True

    async def update_by_id(self, ident: Any, **kwargs) -> Optional[T]:
        """根据 ID 更新指定字段"""
        await self.db.execute(
            update(self.model).where(self.model.id == ident).values(**kwargs)
        )
        return await self.get_by_id(ident)