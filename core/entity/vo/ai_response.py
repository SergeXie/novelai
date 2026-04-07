from pydantic import BaseModel, Field, computed_field
from typing import Optional

class TokenUsage(BaseModel):
    """Token 消耗详情"""
    prompt_tokens: int = Field(default=0, description="输入提示词 Token 数")
    completion_tokens: int = Field(default=0, description="模型输出 Token 数")
    total_tokens: int = Field(default=0, description="总消耗 Token 数")

class AICompletionResponse(BaseModel):
    """AI 生成统一返回结构"""
    content: str = Field(..., description="模型生成的文本内容")
    usage: TokenUsage = Field(default_factory=TokenUsage, description="Token 消耗统计")
    model: Optional[str] = Field(None, description="实际使用的模型名称")
    finish_reason: Optional[str] = Field(None, description="停止原因（如 stop, length）")

class AIWorkFlowStepResponse(BaseModel):
    name:str = Field(..., description="步骤名称")
    result:AICompletionResponse = Field(..., description="生成结果")

class AIWorkFlowResponse(BaseModel):
    context:dict = Field(..., description="工作流上下文")
    steps:list[AIWorkFlowStepResponse] = Field(..., description="工作流分步数据")
    final_result:AICompletionResponse = Field(..., description="生成结果")

class AIUserAssets(BaseModel):
    """用户实时资产余额模型"""
    daily_limit: int = Field(..., description="系统配置的每日免费额度上限")
    used_free: int = Field(..., description="今日已消耗的免费 Token 数")
    monthly_balance: int = Field(..., description="月度会员剩余额度")
    permanent_balance: int = Field(..., description="永久点数剩余余额")

    @computed_field(return_type=int)
    @property
    def free_remaining(self) -> int:
        """动态计算当前剩余的免费额度"""
        return max(0, self.daily_limit - self.used_free)

    class Config:
        # 允许从 SQLAlchemy 模型直接转换
        from_attributes = True