import re

from loguru import logger
from ai.adapters.claude import ClaudeAdapter
from ai.adapters.deep_seek import DeepSeekAdapter
from ai.adapters.doubao import DoubaoAdapter
from ai.adapters.doubao_plus import DoubaoPlusAdapter
from ai.adapters.enums import AIProvider
from ai.adapters.ollama import OllamaAdapter
from common.config.config import settings


class AINexus:
    def __init__(self):
        # 预加载所有支持的适配器
        self._adapters = {
            AIProvider.FREE: OllamaAdapter(),
            AIProvider.DEEPSEEK: DeepSeekAdapter(),
            AIProvider.DOUBAO: DoubaoAdapter(),
            AIProvider.DOUBAOPLUS: DoubaoPlusAdapter(),
            AIProvider.CLAUDE: ClaudeAdapter(),
        }

    # 建议使用忽略大小写的正则匹配
    def filter_ai_content(self, content: str) -> str:
        if not content:
            return ""

        # 匹配 "claude" 或 "anthropic"（忽略大小写）
        # 如果发现包含敏感词，直接返回空字符串
        if re.search(r"claude|anthropic", content, re.IGNORECASE):
            return "暂时无法生成，更改提示词试试。"

        return content

    async def generate_novel_text(self, provider: AIProvider, user_prompt: str, temperature:float, max_tokens: int = None) -> tuple[str, str]:
        print("provider:{}".format(provider))

        system_prompt = settings.ai_system_prompt

        # 1. 根据传入的 provider 获取对应的适配器
        adapter = self._adapters.get(provider)
        if not adapter:
            raise ValueError(f"未支持的模型提供商: {provider}")

        # 2. 调用适配器的统一接口
        content = await adapter.generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )
        try:
            # 假设 filter_ai_content 是你的过滤逻辑
            content = self.filter_ai_content(content)
        except Exception as e:
            # 记录错误原因，但不崩溃
            logger.error(f"AI内容过滤失败: {str(e)}", exc_info=True)
            # 发生异常时的降级处理：清空内容或返回特定提示

        return system_prompt, content

_ai_nexus_instance = AINexus()

def get_ai_nexus() -> AINexus:
    return _ai_nexus_instance