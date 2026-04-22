import asyncio

from loguru import logger
from volcenginesdkarkruntime import Ark

from ai.adapters.base_adapter import OpenAIBaseAdapter
from common.config.config import settings
from core.entity.vo.ai_response import AICompletionResponse, TokenUsage


class DoubaoPlusAdapter(OpenAIBaseAdapter):
    def __init__(self):
        super().__init__(
            name="豆包Pro",
            api_key=settings.doubaoplus.api_key,
            base_url=settings.doubaoplus.base_url,
            model_name=settings.doubaoplus.model_name,
            max_tokens=settings.doubaoplus.max_tokens,
            temperature=settings.doubaoplus.temperature,
        )
        self.ark_client = Ark(
            base_url=settings.doubaoplus.base_url,
            api_key=settings.doubaoplus.api_key,
        )
        self.tools = [
            {
                "type": "web_search",
                "max_keyword": 2,
            }
        ]

    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = None,
        max_tokens: int = None,
        enable_web_search: bool = False,
    ) -> AICompletionResponse:
        if not enable_web_search:
            return await super().generate_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        try:
            final_temperature = temperature if temperature is not None else self.temperature
            final_max_tokens = min(max_tokens or self.max_tokens, self.max_tokens)

            request_kwargs = {
                "model": self.model_name,
                "input": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": final_temperature,
                "max_output_tokens": final_max_tokens,
            }

            if enable_web_search:
                request_kwargs["tools"] = self.tools

            response = await asyncio.to_thread(
                self.ark_client.responses.create,
                **request_kwargs,
            )

            content = self._extract_text(response)
            usage = getattr(response, "usage", None)

            prompt_tokens = getattr(usage, "input_tokens", 0) if usage else 0
            completion_tokens = getattr(usage, "output_tokens", 0) if usage else 0
            total_tokens = getattr(
                usage,
                "total_tokens",
                prompt_tokens + completion_tokens,
            ) if usage else (prompt_tokens + completion_tokens)

            return AICompletionResponse(
                content=content,
                usage=TokenUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                ),
                model=getattr(response, "model", self.model_name),
                finish_reason=self._extract_finish_reason(response),
            )
        except Exception as e:
            info = f"{self.name}[{self.model_name}] 联网生成异常: {str(e)}"
            logger.error(info)
            raise Exception(info)

    @staticmethod
    def _extract_text(response) -> str:
        output_text = getattr(response, "output_text", None)
        if output_text:
            return output_text

        outputs = getattr(response, "output", None) or []
        texts = []

        for item in outputs:
            for content in getattr(item, "content", None) or []:
                text = getattr(content, "text", None)
                if text:
                    texts.append(text)

        return "\n".join(texts).strip()

    @staticmethod
    def _extract_finish_reason(response) -> str:
        outputs = getattr(response, "output", None) or []
        for item in outputs:
            finish_reason = getattr(item, "finish_reason", None)
            if finish_reason:
                return finish_reason
        return "stop"

