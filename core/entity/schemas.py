from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

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
    bid: str
    level: int  # 模型等级
    temperature: float  #
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


class NovelWizardStepRequest(BaseModel):
    step: int = Field(..., ge=1, le=6, description="向导步骤，1-6")
    idea: str = Field(..., description="初步脑洞")
    context: Dict[str, Any] | str = Field(default_factory=dict, description="前序步骤上下文，支持对象或字符串")
    level: int = Field(2, description="模型等级")
    temperature: float = Field(0.8, description="采样温度")
    max_tokens: int = Field(2000, description="生成长度限制")
    chapter_count: int = Field(5, ge=1, le=100, description="第6步章节数量")
    wizardId: Optional[str] = Field(None, description="向导会话ID")


class NovelWizardStepResponse(BaseModel):
    wizardId: str
    requestId: str
    step: int
    stepName: str
    content: str
    parsedContent: Optional[Any] = None
    context: Dict[str, Any] = Field(default_factory=dict)
