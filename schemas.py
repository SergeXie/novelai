from pydantic import BaseModel, Field
from typing import List, Optional

# 定义单个角色
class Character(BaseModel):
    name: str = Field(..., description="角色姓名")
    role: str = Field(..., description="角色定位，如：主角、反派、配角")
    personality: str = Field(..., description="性格特征")
    background: Optional[str] = Field(None, description="背景故事或特殊能力")

# 定义小说设定
class NovelSetting(BaseModel):
    genre: str = Field(..., description="题材，如：玄幻、赛博朋克、言情")
    tone: str = Field("严肃", description="文风基调，如：幽默、黑暗、轻松")
    world_view: Optional[str] = Field(None, description="世界观简述")

# API 请求体
class GenerateRequest(BaseModel):
    # setting: NovelSetting
    # characters: List[Character]
    correlation: list
    user_prompt: str = Field(..., description="当前情节的提示词或指令")
    max_tokens: int = Field(2000, description="生成长度限制")

# 结果微调
class RefineRequest(BaseModel):
    setting: NovelSetting
    characters: List[Character]
    original_content: str = Field(..., description="待修改的原始内容")
    suggestion: str = Field(..., description="用户的修改建议")
    max_tokens: int = Field(2000, description="生成长度限制")
