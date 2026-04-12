from pydantic import BaseModel, Field
from typing import List, Generic, TypeVar

# 定义一个泛型变量 T
T = TypeVar("T")

class PageResp(BaseModel, Generic[T]):
    """通用分页返回模型"""
    list: List[T] = Field(..., description="数据列表")
    total: int = Field(0, description="总条数")
    page: int = Field(1, description="当前页码")
    pageSize: int = Field(10, description="每页数量")