from abc import ABC, abstractmethod
from typing import Optional

from loguru import logger
from openai import AsyncOpenAI

from common.modules.web_search import build_web_search_context
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
            enable_web_search: bool = False,
    ) -> AICompletionResponse:
        """
        所有适配器必须实现的文本生成方法
        """
        pass

class OpenAIBaseAdapter(BaseAIAdapter):
    def __init__(self, name:str, api_key:str, base_url:str, model_name:str, max_tokens:int, temperature:float):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.name = name

    async def _build_user_prompt_with_web_search(
            self,
            user_prompt: str,
            enable_web_search: bool,
    ) -> str:
        if not enable_web_search:
            return user_prompt

        try:
            search_context = await build_web_search_context(user_prompt)
        except Exception as exc:
            logger.warning(f"{self.name} 联网搜索失败，改为普通生成: {exc}")
            return user_prompt

        if not search_context:
            return user_prompt

        return (
            f"用户问题：\n{user_prompt}\n\n"
            f"{search_context}\n\n"
            "请结合以上联网搜索结果回答用户问题；若搜索结果不足以支撑结论，请明确说明。"
        )
        
    async def generate_text(
            self,
            system_prompt: str,
            user_prompt: str,
            temperature: float = None,
            max_tokens: int = None,
            context_messages: Optional[list[dict]] = None,
            enable_web_search: bool = False,
    ) -> AICompletionResponse:  # 指定返回类型
        print("@@@查看max_tokens",max_tokens)
        try:
            final_user_prompt = await self._build_user_prompt_with_web_search(
                user_prompt=user_prompt,
                enable_web_search=enable_web_search,
            )
            messages = [
                {"role": "system", "content": system_prompt},
            ]
            if context_messages:
                messages += context_messages
            messages.append({"role": "user", "content": final_user_prompt})
            
            final_max_tokens = max_tokens if max_tokens else self.max_tokens
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature or self.temperature,
                max_tokens=final_max_tokens)

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