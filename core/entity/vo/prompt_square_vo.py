from pydantic import BaseModel, field_serializer, Field
from typing import List, Optional


from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime


class PromptItem(BaseModel):
    """
    提示词完整信息（全字段返回）
    """

    id: int

    # 唯一标识
    template_key: str

    # 基础信息
    title: str
    description: str
    cover_img: Optional[str]

    # 分类 & 标签
    category: str
    tags: Optional[List[str]]

    # 核心内容（前端编辑需要）
    content: str
    engine_type: str
    input_schema: Dict

    # 作者信息
    author_id: int

    # 统计
    use_count: int

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


class PromptSquareCreateReq(BaseModel):
    title: str
    category: str
    content: str
    description: str = ""
    status: int = 1


class PromptSquareUpdateReq(BaseModel):
    id: int = Field(..., gt=0)
    title: str
    category: str
    content: str
    description: str = ""
    status: int = 1
