from typing import List, Optional

from pydantic import BaseModel, Field

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