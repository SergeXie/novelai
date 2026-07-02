from typing import Optional

from loguru import logger

from ai.adapters.base_adapter import OpenAIBaseAdapter
from common.config.config import settings
from core.entity.vo.ai_response import AICompletionResponse, TokenUsage


class MimoAdapter(OpenAIBaseAdapter):
    def __init__(self):
        super().__init__(name="Mimo",
                         api_key=settings.mimo.api_key,
                         base_url=settings.mimo.base_url,
                         model_name=settings.mimo.model_name,
                         max_tokens=settings.mimo.max_tokens,
                         temperature=settings.mimo.temperature)

    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = None,
        max_tokens: int = None,
        context_messages: Optional[list[dict]] = None,
        enable_web_search: bool = False,
    ) -> AICompletionResponse:
        try:
            final_user_prompt = await self._build_user_prompt_with_web_search(
                user_prompt=user_prompt,
                enable_web_search=enable_web_search,
            )
            if max_tokens:
                range_offset = 300 if max_tokens >= 2000 else 200
                min_tokens = max_tokens - range_offset
                max_tokens_range = max_tokens + range_offset
                final_user_prompt = f"{final_user_prompt}\n\n【字数硬性要求：{min_tokens}~{max_tokens_range}字】\n这是不可协商的范围限制。不足{min_tokens}字视为未完成，超过{max_tokens_range}字视为违规。请精准控制篇幅，确保一次输出达标。"
            final_temperature = temperature if temperature is not None else self.temperature
            final_max_tokens = min(max_tokens or self.max_tokens, self.max_tokens)

            messages = [
                {"role": "system", "content": system_prompt},
            ]
            if context_messages:
                messages += context_messages
            messages.append({"role": "user", "content": final_user_prompt})

            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_completion_tokens=final_max_tokens,
                temperature=final_temperature,
                top_p=0.95,
                stream=False,
                stop=None,
                frequency_penalty=0,
                presence_penalty=0,
            )

            return AICompletionResponse(
                content=response.choices[0].message.content,
                usage=TokenUsage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens,
                ),
                model=response.model,
                finish_reason=response.choices[0].finish_reason,
            )
        except Exception as e:
            info = f"{self.name}[{self.model_name}] 生成异常: {str(e)}"
            logger.error(info)
            raise Exception(info)