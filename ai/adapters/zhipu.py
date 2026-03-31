from ai.adapters.base_adapter import BaseAIAdapter
import asyncio

from openai import OpenAI
from loguru import logger

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

    async def generate_text(self, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int = None) -> str:
        if not self.client:
            info = "智谱客户端未初始化，请检查配置或安装相应 SDK。"
            logger.error(info)
            raise Exception(info)

        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature or self.temperature,
                max_tokens=max_tokens or self.max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            info = f"智谱 AI响应异常: {str(e)}"
            logger.error(info)
            raise Exception(info)