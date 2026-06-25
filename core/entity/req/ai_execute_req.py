from typing import Optional, List, Dict
from pydantic import BaseModel, Field

# 定义请求体 Pydantic 模型
class AIExecuteReq(BaseModel):
    level: int = Field(..., description="AI 生成级别")
    temperature: float = Field(0.7, description="生成温度")
    maxTokens: Optional[int] = Field(None, description="最大生成 Token 数量")
    templateKey: Optional[str] = Field(None, description="模板 Key")
    tool_key: Optional[str] = Field(None, description="工具 Key")
    inputs: Optional[Dict] = Field(None, description="模板输入参数")
    userPrompt: str = Field("", description="用户提示词")
    bid: Optional[str] = Field(None, description="书籍 ID")
    correlation: Optional[List[str]] = Field(None, description="关联 ID 列表")