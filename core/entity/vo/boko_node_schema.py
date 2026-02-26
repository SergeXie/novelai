from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


class NodeTreeSchema(BaseModel):
    id: int
    bid: str
    name: str
    content: Optional[str] = None
    parent_id: Optional[int] = None
    is_leaf: int = 0

    children:Optional[List["NodeTreeSchema"]] = None

    class Config:
        from_attributes = True


# 核心：解析递归引用
NodeTreeSchema.model_rebuild()