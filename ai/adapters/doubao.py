from ai.adapters.base_adapter import OpenAIBaseAdapter
from common.config.config import settings

class DoubaoAdapter(OpenAIBaseAdapter):
    def __init__(self):
        super().__init__(name="豆包",
                         api_key=settings.doubao.api_key,
                         base_url=settings.doubao.base_url,
                         model_name=settings.doubao.model_name,
                         max_tokens=settings.doubao.max_tokens,
                         temperature=settings.doubao.temperature
                         )