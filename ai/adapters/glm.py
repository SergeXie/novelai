from ai.adapters.base_adapter import OpenAIBaseAdapter
from common.config.config import settings

class GLMAdapter(OpenAIBaseAdapter):
    def __init__(self):
        super().__init__(name="智谱",
                         api_key=settings.zhipu.api_key,
                         base_url=settings.zhipu.base_url,
                         model_name=settings.zhipu.model_name,
                         max_tokens=settings.zhipu.max_tokens,
                         temperature=settings.zhipu.temperature)