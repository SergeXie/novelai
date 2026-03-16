from ai.adapters.base_adapter import BaseAIAdapter
import asyncio

from loguru import logger

from common.config.config import settings


class GeminiAdapter(BaseAIAdapter):
    def __init__(self):
        # 使用 settings 中嵌套的 gemini 配置
        # 这里尽量兼容不同的客户端实现：默认尝试使用 OpenAI 客户端结构，
        # 如果需要可以替换为 Google Gemini 的实际客户端初始化。
        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=settings.gemini.api_key,
                base_url=settings.gemini.base_url
            )
        except Exception:
            self.client = None

        self.model_name = settings.gemini.model_name
        self.max_tokens = settings.gemini.max_tokens
        self.temperature = settings.gemini.temperature
        self.multiplier = settings.gemini.multiplier

    async def generate_text(self, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int = None) -> str:
        if not self.client:
            info = "Gemini 客户端未初始化，请检查配置或安装相应 SDK。"
            logger.error(info)
            raise Exception(info)

        try:
            # 使用 to_thread 避免阻塞主事件循环
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
            info = f"Gemini AI响应异常: {str(e)}"
            logger.error(info)
            raise Exception(info)
