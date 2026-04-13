from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Dict, Any
from datetime import datetime

# 1. 基础属性
class PromptRegistryBase(BaseModel):
    tool_key: str = Field(..., description="工具唯一标识", min_length=2, max_length=64)
    name: str = Field(..., description="工具名称", max_length=128)
    variables_schema: Dict[str, Any] = None

class PromptRegistryResp(PromptRegistryBase):

    model_config = ConfigDict(
        from_attributes=True,
        # 格式化时间输出
        json_encoders={datetime: lambda v: v.strftime("%Y-%m-%d %H:%M:%S")}
    )

    @field_validator("variables_schema", mode="before")
    @classmethod
    def ensure_dict(cls, v: Any) -> Dict[str, Any]:
        """
        容错处理：如果数据库存的是 JSON 字符串，自动转为字典
        """
        import json
        if isinstance(v, str):
            try:
                return json.loads(v)
            except:
                return {}
        return v or {}