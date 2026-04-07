from ai.adapters.base_adapter import OpenAIBaseAdapter
from common.config.config import settings

class GPTAdapter(OpenAIBaseAdapter):
    def __init__(self):
        super().__init__(name="GPT",
                         api_key=settings.gpt.api_key,
                         base_url=settings.gpt.base_url,
                         model_name=settings.gpt.model_name,
                         max_tokens=settings.gpt.max_tokens,
                         temperature=settings.gpt.temperature)
