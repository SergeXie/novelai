from ai.adapters.base_adapter import OpenAIBaseAdapter
from common.config.config import settings

class ClaudeThinkingAdapter(OpenAIBaseAdapter):
    def __init__(self):
        # 使用 settings 中嵌套的 claude 配置
        super().__init__(name="Claudethinking",
                         api_key=settings.claudethinking.api_key,
                         base_url=settings.claudethinking.base_url,
                         model_name=settings.claudethinking.model_name,
                         max_tokens=settings.claudethinking.max_tokens,
                         temperature=settings.claudethinking.temperature
                         )