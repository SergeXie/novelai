from ai.adapters.base_adapter import BaseAIAdapter
import asyncio

from openai import OpenAI
from loguru import logger

from common.config.config import settings

class ClaudeAdapter(BaseAIAdapter):
    def __init__(self):
        # 使用 settings 中嵌套的 claude 配置
        self.client = OpenAI(
            api_key=settings.claude.api_key,
            base_url=settings.claude.base_url
        )
        self.model_name = settings.claude.model_name
        self.max_tokens = settings.claude.max_tokens
        self.temperature = settings.claude.temperature
        self.multiplier = settings.claude.multiplier

    async def generate_text(self, system_prompt: str, user_prompt: str, temperature:float, max_tokens: int = None) -> str:
        try:
            # 使用 to_thread 避免阻塞
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
            info = f"Claude AI响应异常: {str(e)}"
            logger.error(info)
            raise Exception(info)