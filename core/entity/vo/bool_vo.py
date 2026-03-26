from typing import List

from pydantic import BaseModel, Field


class Character(BaseModel):
    """角色卡模型"""
    name: str = Field(..., description="角色姓名")
    role: str = Field(..., description="角色定位或身份描述")

class AutoCreateBookReq(BaseModel):
    """作品完整数据模型"""
    title: str = Field(..., description="作品标题")
    summary: str = Field(..., description="作品简介/概要")
    characters: List[Character] = Field(None, description="核心角色列表")