import asyncio
from abc import ABC, abstractmethod
from typing import Optional

from loguru import logger
from openai import OpenAI, AsyncOpenAI

from core.entity.vo.ai_response import AICompletionResponse, TokenUsage


class BaseAIAdapter(ABC):
    @abstractmethod
    async def generate_text(
            self,
            system_prompt: str,
            user_prompt: str,
            temperature: float,
            max_tokens: int = None,
            context_messages: Optional[list[dict]] = None,
    ) -> AICompletionResponse:
        """
        所有适配器必须实现的文本生成方法
        """
        pass

class OpenAIBaseAdapter(BaseAIAdapter):
    def __init__(self, name:str, api_key:str, base_url:str, model_name:str, max_tokens:int, temperature:float):
        # 使用 settings 中嵌套的 deepseek 配置
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.name = name
        
    async def generate_text(
            self,
            system_prompt: str,
            user_prompt: str,
            temperature: float = None,
            max_tokens: int = None,
            context_messages: Optional[list[dict]] = None,
    ) -> AICompletionResponse:  # 指定返回类型
        try:
            messages = [
                {"role": "system", "content": system_prompt},
            ]
            if context_messages:
                messages += context_messages
            messages.append({"role": "user", "content": user_prompt})
            
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature or self.temperature,
                max_tokens=min(max_tokens or self.max_tokens, self.max_tokens))

            # 封装为 Pydantic 对象
            return AICompletionResponse(
                content=response.choices[0].message.content,
                usage=TokenUsage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens
                ),
                model=response.model,
                finish_reason=response.choices[0].finish_reason
            )
        except Exception as e:
            info = f"{self.name}[{self.model_name}] 生成异常: {str(e)}"
            logger.error(info)
            raise Exception(info)