from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_serializer, Field

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
    max_tokens: int
    temperature: Decimal
    context_window: int
    weight: int
    status: int

    model_config = ConfigDict(from_attributes=True)


class DeleteHistoryReq(BaseModel):
    requestIds: list


# --- 1. 定义具体的条目模型 ---
class AIGenerateLogResp(BaseModel):
    id:int
    requestId: str
    prompt: str
    status: int
    action: str
    totalTokens: int
    model: str
    # 将 outputContent 设置为 Optional，兼容 defer() 没查出来的情况
    outputContent: Optional[str] = Field(None, description="模型输出内容")
    createdAt: datetime

    @field_serializer('createdAt')
    def serialize_dt(self, dt: datetime):
        return dt.strftime('%Y-%m-%d %H:%M:%S') if dt else None

    @classmethod
    async def _get_base_data(cls, log: "AiNovelGenerateLog", model_dao: "AiModelDAO") -> dict:
        """提取公共的数据处理逻辑"""
        prompt_content = log.originPrompt or ""
        prompt_preview = (prompt_content[:200] + "...") if len(prompt_content) > 200 else prompt_content
        model_name = await model_dao.get_model_name_by_identifier(log.model)

        # --- 修复点：安全获取 outputContent ---
        # 不要直接 log.outputContent，那样会触发 MissingGreenlet
        # 只有当 outputContent 确实在内存里（没被 defer）时才读取
        output_data = None
        if 'outputContent' in log.__dict__:
            output_data = log.outputContent
        # ------------------------------------

        return {
            "id":log.id,
            "requestId": log.requestId,
            "prompt": prompt_preview,
            "model": model_name,
            "status": log.status,
            "action": log.actionType,
            "totalTokens": int(log.actualAmount or 0),
            "createdAt": log.createdAt,
            "outputContent": output_data,
        }

    @classmethod
    async def from_orm_model(cls, log: "AiNovelGenerateLog", model_dao: "AiModelDAO") -> "AIGenerateLogResp":
        data = await cls._get_base_data(log, model_dao)
        return cls(**data)

    @classmethod
    async def from_orm_model(cls, log: "AiNovelGenerateLog", model_dao: "AiModelDAO") -> "AIGenerateLogResp":
        data = await cls._get_base_data(log, model_dao)
        return cls(**data)

class AIGenerateLogDetailResp(AIGenerateLogResp):
    outputContent: str
    originPrompt: str

    @staticmethod
    def _format_detail_output(
            action_type: str,
            output_content: str | None,
            template_key: str | None = None,
    ) -> str:
        action = (action_type or "").lower()
        if action in {"workflow", "workflow_step"}:
            return "格式化生成内容"
        if action == "execute" and (template_key or "").lower() in {"role", "universe"}:
            return "模版化生成内容"
        return output_content or ""

    @classmethod
    async def from_orm_model(cls, log: "AiNovelGenerateLog", model_dao: "AiModelDAO") -> "AIGenerateLogDetailResp":
        # 调用公共逻辑获取字典，而不是获取实例
        data = await cls._get_base_data(log, model_dao)

        # 补全详情特有字段
        data.update({
            "totalTokens": int(log.actualAmount or 0),
            "outputContent": cls._format_detail_output(log.actionType, log.outputContent, log.template_key),
            "originPrompt": log.originPrompt or ""
        })

        # 此时实例化子类，校验一次性通过
        return cls(**data)
