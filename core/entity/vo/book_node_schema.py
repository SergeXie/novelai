import json
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import Query
from pydantic import BaseModel, Field, field_serializer, ConfigDict, field_validator

from common.config.config import settings

class NodeTreeSchema(BaseModel):
    id: int
    bid: str
    uid: int
    name: str
    # content: Optional[str] = None
    parent_id: Optional[int] = None
    is_leaf: int = 0
    type: int = 0
    book_len: Optional[int] = 0
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="扩展配置数据"
    )

    children:Optional[List["NodeTreeSchema"]] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("data", mode="before")
    @classmethod
    def transform_json_to_dict(cls, v: Any) -> Dict[str, Any]:
        """
        核心修复逻辑：
        如果数据库读取出来的是字符串（JSON 字符串），自动转为字典。
        """
        if isinstance(v, str):
            try:
                # 处理你之前提到的 {\"name\":\"晓燕\"...} 这种转义字符串
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return {}
        if v is None:
            return {}
        return v

    @field_validator("book_len", mode="before")
    @classmethod
    def normalize_book_len(cls, v: Any) -> int:
        return int(v or 0)

class CreateBookReq(BaseModel):
    """创建书籍请求参数"""
    template_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    coverUrl: Optional[str] = Field(default=None, max_length=512, description="书籍封面图片地址")


class BookResp(BaseModel):
    """书籍完整返回对象（与 books 表字段一一对应）"""
    id: int
    uid: int
    bid: str
    title: str
    bookType:str
    description: Optional[str]
    coverUrl: Optional[str] = None
    status: int
    wordCount: int
    template_id: Optional[str]
    createTime: datetime
    updateTime: datetime

    # 关键点 1：mode="plain"
    @field_serializer("createTime", "updateTime", mode="plain")
    def serialize_datetime(self, value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")

    @field_serializer("coverUrl", mode="plain")
    def serialize_cover_url(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return value

        if value.startswith("http://") or value.startswith("https://"):
            return value

        cloud_address = (settings.CLOUD_ADDRESS or "").rstrip("/")
        if not cloud_address:
            return value

        return f"{cloud_address}/{value.lstrip('/')}"

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
    is_leaf: int
    content: Optional[str]
    name: str
    type: int = 0
    depth: int = 0
    createTime: datetime
    updateTime: datetime

    # 扩展字段
    # 使用 Dict[str, Any] 对应数据库的 JSON 类型
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="扩展配置数据"
    )

    @field_serializer("createTime", "updateTime", mode="plain")
    def serialize_datetime(self, value: datetime) -> str:
        """
        时间字段统一序列化为字符串（无 T）
        """
        return value.strftime("%Y-%m-%d %H:%M:%S")

    model_config = ConfigDict(from_attributes=True)


class BookSearchSnippetItem(BaseModel):
    snippet: str


class BookSearchChapterItem(BaseModel):
    nodeId: int
    chapterName: str
    matchCount: int
    snippets: List[BookSearchSnippetItem]


class BookSearchResp(BaseModel):
    keyword: str
    total: int
    list: List[BookSearchChapterItem]


class UpdateBookNodeReq(BaseModel):
    """
    编辑书籍节点请求参数
    """
    id: int = Query(..., description="mc_book_node 节点ID"),
    bid: str = Query(..., description="mc_book_node bid ID"),
    content: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    len: Optional[int] = None


class EditBookNodeReq(BaseModel):
    """
    编辑章节 / 节点请求
    """
    id: int
    bid:str
    name: Optional[str] = None
    data: Optional[str] = None


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
    data: Optional[str] = None
    content: Optional[str] = None
    type: int


class AddChapterResp(BaseModel):
    """
    新增章节返回
    """
    id: int
    bid: str
    parent_id: int
    is_leaf: int
    name: str
    data: Optional[Dict[str, Any]] = None
    content: Optional[str] = None



class DeleteBookNodeReq(BaseModel):
    id: int
    bid: str


class OfflineBookReq(BaseModel):
    """
    下架书籍请求
    """
    bid: str


class EditBookReq(BaseModel):
    """
    编辑书籍信息请求
    """
    bid: str
    template_id: Optional[str] = None
    bookType: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    coverUrl: Optional[str] = Field(default=None, max_length=512, description="书籍封面图片地址")



class HardDeleteBookReq(BaseModel):
    bid: str

# 核心：解析递归引用
NodeTreeSchema.model_rebuild()
