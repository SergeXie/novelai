from ai.adapters.base_adapter import OpenAIBaseAdapter
from common.config.config import settings


class DeepSeekAdapter(OpenAIBaseAdapter):
    def __init__(self):
        super().__init__(name="Deepseek",
                         api_key=settings.deepseek.api_key,
                         base_url=settings.deepseek.base_url,
                         model_name=settings.deepseek.model_name,
                         max_tokens=settings.deepseek.max_tokens,
                         temperature=settings.deepseek.temperature
                         )
