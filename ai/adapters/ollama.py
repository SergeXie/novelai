from ai.adapters.base_adapter import OpenAIBaseAdapter
from common.config.config import settings

class OllamaAdapter(OpenAIBaseAdapter):
    def __init__(self):
        super().__init__(name="ollama",
                         api_key=settings.free.api_key,
                         base_url=settings.free.base_url,
                         model_name=settings.free.model_name,
                         max_tokens=settings.free.max_tokens,
                         temperature=settings.free.temperature)