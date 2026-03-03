# --- 1. 定义具体模型的配置结构 ---
from pydantic import BaseModel


class LLMProviderConfig(BaseModel):
    api_key: str
    base_url: str
    model_name: str
    multiplier: float = 1.0
    max_tokens: int = 32000
    temperature: float = 0.7