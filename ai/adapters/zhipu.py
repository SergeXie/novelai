from ai.adapters.base_adapter import BaseAIAdapter
import asyncio

from loguru import logger
from openai import OpenAI

from common.config.config import settings


class ZhipuAdapter(BaseAIAdapter):
    def __init__(self):
        try:
            self.client = OpenAI(
                api_key=settings.zhipu.api_key,
                base_url=settings.zhipu.base_url
            )
        except Exception:
            self.client = None

        self.model_name = settings.zhipu.model_name
        self.max_tokens = settings.zhipu.max_tokens
        self.temperature = settings.zhipu.temperature
        self.multiplier = settings.zhipu.multiplier

    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int = None
    ) -> str:
        if not self.client:
            info = "智谱客户端未初始化，请检查 ZHIPU 配置或 SDK 安装。"
            logger.error(info)
            raise Exception(info)

        system_prompt = (system_prompt or "").strip()
        user_prompt = (user_prompt or "").strip()

        if not user_prompt:
            info = "智谱请求失败：user_prompt 不能为空。"
            logger.error(info)
            raise ValueError(info)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model_name,
                messages=messages,
                max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
                temperature=temperature if temperature is not None else self.temperature,
            )
            return response.choices[0].message.content
        except Exception as e:
            info = f"智谱AI响应异常: {str(e)}"
            logger.error(info)
            raise Exception(info)