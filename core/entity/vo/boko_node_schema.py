from datetime import datetime
from typing import List, Optional

from fastapi import Query
from pydantic import BaseModel, Field, model_validator, field_serializer, ConfigDict


class NodeTreeSchema(BaseModel):
    id: int
    bid: str
    uid: int
    name: str
    # content: Optional[str] = None
    parent_id: Optional[int] = None
    is_leaf: int = 0

    children:Optional[List["NodeTreeSchema"]] = None

    class Config:
        from_attributes = True

class CreateBookReq(BaseModel):
    """创建书籍请求参数"""
    bookType: str
    title: str
    description: Optional[str] = None


class BookResp(BaseModel):
    """书籍完整返回对象（与 books 表字段一一对应）"""
    id: int
    uid: int
    bid: str
    title: str
    bookType:str
    description: Optional[str]
    status: int
    wordCount: int
    createTime: datetime
    updateTime: datetime

    # 关键点 1：mode="plain"
    @field_serializer("createTime", "updateTime", mode="plain")
    def serialize_datetime(self, value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")

    # 关键点 2：model_config（不是 class Config）
    model_config = ConfigDict(
        from_attributes=True
    )


class BookNodeDetailResp(BaseModel):
    """
    书籍节点详情返回对象
    """

    id: int
    bid: str
    uid: int
    content: Optional[str]
    name: Optional[str]
    createTime: datetime
    updateTime: datetime

    @field_serializer("createTime", "updateTime", mode="plain")
    def serialize_datetime(self, value: datetime) -> str:
        """
        时间字段统一序列化为字符串（无 T）
        """
        return value.strftime("%Y-%m-%d %H:%M:%S")

    model_config = ConfigDict(from_attributes=True)


class UpdateBookNodeReq(BaseModel):
    """
    编辑书籍节点请求参数
    """
    id: int = Query(..., description="mc_book_node 节点ID"),
    bid: str = Query(..., description="mc_book_node bid ID"),
    content: Optional[str] = None


class EditBookNodeReq(BaseModel):
    """
    编辑章节 / 节点请求
    """
    id: int
    bid:str
    name: Optional[str] = None


class EditBookNodeResp(BaseModel):
    """
    编辑后返回的节点信息
    """
    id: int
    name: str
    updateTime: datetime

    @field_serializer("updateTime", mode="plain")
    def serialize_datetime(self, value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")

    model_config = ConfigDict(from_attributes=True)


class AddBookNodeReq(BaseModel):
    """
    在指定父节点下新增节点
    """
    bid: str
    parent_id: int
    is_leaf: int
    name: str


class AddChapterResp(BaseModel):
    """
    新增章节返回
    """
    id: int
    bid: str
    parent_id: int
    is_leaf: int
    name: str


class DeleteBookNodeReq(BaseModel):
    id: int
    bid: str


class OfflineBookReq(BaseModel):
    """
    下架书籍请求
    """
    bid: str

# 核心：解析递归引用
NodeTreeSchema.model_rebuild()