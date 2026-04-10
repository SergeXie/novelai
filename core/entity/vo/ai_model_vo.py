from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_serializer

from core.entity.do.generate_log import AiNovelGenerateLog
from dao.ai_model_dao import AiModelDAO


class AiModelResp(BaseModel):
    """
    AI 模型响应对象（全部字段返回）
    """

    id: int
    level: int
    model_name: str
    multiplier: Decimal

    model_config = ConfigDict(from_attributes=True)


class DeleteHistoryReq(BaseModel):
    requestIds: list


# --- 1. 定义具体的条目模型 ---
class AIGenerateLogResp(BaseModel):
    requestId: str
    prompt: str
    status: int
    action: str
    totalTokens:int
    model:str
    actualAmount:int
    createdAt: datetime

    @field_serializer('createdAt')
    def serialize_dt(self, dt: datetime):
        return dt.strftime('%Y-%m-%d %H:%M:%S')

    @classmethod
    async def _get_base_data(cls, log: "AiNovelGenerateLog", model_dao: "AiModelDAO") -> dict:
        """提取公共的数据处理逻辑"""
        prompt_content = log.originPrompt or ""
        prompt_preview = (prompt_content[:200] + "...") if len(prompt_content) > 200 else prompt_content
        model_name = await model_dao.get_model_name_by_identifier(log.model)

        return {
            "requestId": log.requestId,
            "prompt": prompt_preview,
            "model": model_name,
            "status": log.status,
            "action": log.actionType,
            "totalTokens": log.totalTokens,
            "actualAmount": log.actualAmount,
            "createdAt": log.createdAt
        }

    @classmethod
    async def from_orm_model(cls, log: "AiNovelGenerateLog", model_dao: "AiModelDAO") -> "AIGenerateLogResp":
        data = await cls._get_base_data(log, model_dao)
        return cls(**data)

class AIGenerateLogDetailResp(AIGenerateLogResp):
    outputContent: str
    originPrompt: str

    @classmethod
    async def from_orm_model(cls, log: "AiNovelGenerateLog", model_dao: "AiModelDAO") -> "AIGenerateLogDetailResp":
        # 调用公共逻辑获取字典，而不是获取实例
        data = await cls._get_base_data(log, model_dao)

        # 补全详情特有字段
        data.update({
            "outputContent": log.outputContent or "",
            "originPrompt": log.originPrompt or ""
        })

        # 此时实例化子类，校验一次性通过
        return cls(**data)