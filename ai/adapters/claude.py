from ai.adapters.base_adapter import OpenAIBaseAdapter
from common.config.config import settings

class ClaudeAdapter(OpenAIBaseAdapter):
    def __init__(self):
        # 使用 settings 中嵌套的 claude 配置
        super().__init__(name="Claude",
                         api_key=settings.claude.api_key,
                         base_url=settings.claude.base_url,
                         model_name=settings.claude.model_name,
                         max_tokens=settings.claude.max_tokens,
                         temperature=settings.claude.temperature
                         )