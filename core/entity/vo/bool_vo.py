from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict


class Character(BaseModel):
    """角色卡模型"""
    name: str = Field(..., description="角色姓名")
    role: str = Field(..., description="角色定位或身份描述")

class ChapterData(BaseModel):
    """章节模型"""
    title: str = Field(..., description="章节标题")
    content: Optional[str] = Field(None, description="章节正文内容")
    index: int = Field(..., description="章节排序序号")

class AutoCreateBookReq(BaseModel):
    """作品完整数据模型"""
    title: str = Field(..., description="作品标题")
    summary: str = Field(..., description="作品简介/概要")

    # 核心角色列表
    characters: List[Character] = Field(default_factory=list, description="核心角色列表")

    # 新增：章节数组字段
    chapters: List[ChapterData] = Field(
        default_factory=list,
        description="已生成的章节列表"
    )

    # 可选：如果大纲只是简单的文本，也可以增加一个全局大纲字段
    fullOutlineText: Optional[str] = Field("", description="全局未拆分的长文本大纲")

    writingStyle: Optional[str] = Field("", description="写作手法")
    worldView: Optional[str] = Field("", description="世界观")

class BookAssetVO(BaseModel):
    """
    拆书资产展示对象 (VO)
    仅展示标题、创建时间以及用于前端定位的 requestId
    """
    title: str
    created_at: datetime
    request_id: str  # 建议保留此字段，方便前端点击列表项时反查详情

    # Pydantic v2 配置，允许从 SQLAlchemy 模型直接转换
    model_config = ConfigDict(from_attributes=True)

    # 如果需要自定义时间格式输出（例如：2026-04-30 14:00:00）
    # 可以添加一个验证器或在前端处理