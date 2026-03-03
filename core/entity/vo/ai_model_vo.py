from pydantic import BaseModel, ConfigDict, field_serializer
from datetime import datetime
from decimal import Decimal


class AiModelResp(BaseModel):
    """
    AI 模型响应对象（全部字段返回）
    """

    id: int
    level: int
    model_name: str
    multiplier: Decimal

    model_config = ConfigDict(from_attributes=True)