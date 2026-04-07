from ai.adapters.base_adapter import OpenAIBaseAdapter
from common.config.config import settings

class DoubaoPlusAdapter(OpenAIBaseAdapter):
    def __init__(self):
        super().__init__(name="豆包Pro",
                         api_key=settings.doubaoplus.api_key,
                         base_url=settings.doubaoplus.base_url,
                         model_name=settings.doubaoplus.model_name,
                         max_tokens=settings.doubaoplus.max_tokens,
                         temperature=settings.doubaoplus.temperature
                         )

