# -*- coding: utf-8 -*-
from ai.adapters.base_adapter import BaseAIAdapter
import asyncio

from openai import OpenAI
from loguru import logger

from common.config.config import settings


class OllamaAdapter(BaseAIAdapter):
    def __init__(self):
        # 使用 settings 中嵌套的 free 配置（用于Ollama）
        self.client = OpenAI(
            api_key=settings.free.api_key or "ollama",  # Ollama通常不需要API密钥
            base_url=settings.free.base_url
        )
        self.model_name = settings.free.model_name
        self.max_tokens = settings.free.max_tokens
        self.temperature = settings.free.temperature
        self.multiplier = settings.free.multiplier

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
            # 确保错误信息正确处理 UTF-8 编码
            error_msg = str(e).encode('utf-8', errors='replace').decode('utf-8')
            info = f"Ollama AI响应异常: {error_msg}"
            logger.error(info)
            raise Exception(info)