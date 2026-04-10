from pydantic import BaseModel, Field
from typing import List, Generic, TypeVar, Any

# 定义一个泛型变量 T
T = TypeVar("T")

class PageResult(BaseModel, Generic[T]):
    """通用分页返回模型"""
    list: List[T] = Field(..., description="数据列表")
    total: int = Field(0, description="总条数")
    page: int = Field(1, description="当前页码")
    size: int = Field(10, description="每页数量")