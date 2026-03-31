from ai.adapters.base_adapter import BaseAIAdapter
import asyncio

from openai import OpenAI
from loguru import logger

from common.config.config import settings


class GPTAdapter(BaseAIAdapter):
    def __init__(self):
        
        
        
        try:
            self.client = OpenAI(
                api_key=settings.gpt.api_key,
                base_url=settings.gpt.base_url
            )
        except Exception:
            self.client = None

        self.model_name = settings.gpt.model_name
        self.max_tokens = settings.gpt.max_tokens
        self.temperature = settings.gpt.temperature
        self.multiplier = settings.gpt.multiplier

    async def generate_text(self, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int = None) -> str:
        if not self.client:
            info = "GPT 客户端未初始化，请检查配置或安装相应 SDK。"
            logger.error(info)
            raise Exception(info)
        
        print('@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@')

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
            info = f"GPT AI响应异常: {str(e)}"
            logger.error(info)
            raise Exception(info)
