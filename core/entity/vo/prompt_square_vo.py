from datetime import datetime
from typing import List, Optional, Dict

from pydantic import BaseModel
from pydantic import field_serializer


class PromptItem(BaseModel):
    """
    提示词完整信息（全字段返回）
    """

    # 唯一标识
    template_key: str

    # 基础信息
    title: str
    description: str
    cover_img: Optional[str]

    # 分类 & 标签
    category: str
    tags: Optional[str]

    # 核心内容（前端编辑需要）
    input_schema: Dict

    # 作者信息
    author_id: int

    # 统计
    use_count: int

    # 状态
    status: int

    audit_reason:str

    # 时间
    created_at: datetime
    updated_at: datetime


    # ==================== 时间格式化 ====================

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: datetime):
        """
        将 datetime 转成字符串
        """
        if value:
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return None

class PromptListItemResp(PromptItem):
    """
    提示词列表项（带权限）
    """
    can_edit: bool
    favor_count: int = 0
    is_favorited: bool = False

class PromptItemDetail(BaseModel):
    """
    提示词完整信息（全字段返回）
    """

    # 唯一标识
    template_key: str

    # 基础信息
    title: str
    description: str

    input_schema: Dict

    # 分类 & 标签
    category: str

    # 核心内容（前端编辑需要）
    content: str

    # 状态
    status: int

    # 时间
    created_at: datetime
    updated_at: datetime

    # ==================== 时间格式化 ====================

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: datetime):
        """
        将 datetime 转成字符串
        """
        if value:
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return None




class PromptListResponse(BaseModel):
    """
    分页返回
    """

    list: List[PromptItem]
    total: int


class PromptCategoryItem(BaseModel):
    """
    提示词分类项
    """

    category: str


class PromptToolMenuItem(BaseModel):
    template_key: str
    title: str
    description: str
    cover_img: Optional[str] = ""
    # content: str
    category: str


class PromptTemplateBriefItem(BaseModel):
    template_key: str
    title: str
    description: str


class PromptSquareCreateReq(BaseModel):
    title: str
    category: str
    content: str
    description: str = ""
    status: int = 0


class PromptSquareUpdateReq(BaseModel):
    template_key: str
    title: str
    category: str
    content: str
    description: str = ""
    status: int = 0


class PromptDetailResp(PromptItemDetail):
    """
    提示词详情（带权限信息）
    """

    can_edit: bool
    favor_count: int = 0
    is_favorited: bool = False



class PromptSquareDetailReq(BaseModel):
    template_key: str

