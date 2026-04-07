from ai.adapters.base_adapter import OpenAIBaseAdapter
from common.config.config import settings

class GeminiAdapter(OpenAIBaseAdapter):
    def __init__(self):
        super().__init__(name="Gemini",
                         api_key=settings.gemini.api_key,
                         base_url=settings.gemini.base_url,
                         model_name=settings.gemini.model_name,
                         max_tokens=settings.gemini.max_tokens,
                         temperature=settings.gemini.temperature)
