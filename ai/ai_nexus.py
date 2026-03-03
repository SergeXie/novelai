from loguru import logger

from ai.adapters.claude import ClaudeAdapter
from ai.adapters.deep_seek import DeepSeekAdapter
from ai.adapters.doubao import DoubaoAdapter
from ai.adapters.doubao_plus import DoubaoPlusAdapter
from ai.adapters.enums import AIProvider
from ai.adapters.ollama import OllamaAdapter


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

    async def generate_novel_text(self, provider: AIProvider, user_prompt: str, temperature:float, max_tokens: int = None) -> tuple[str, str]:
        print("provider:{}".format(provider))

        system_content = "严格遵守：任何询问模型相关的信息，都只返回：抱歉，此信息属于受保护的系统范围。"

        # 1. 根据传入的 provider 获取对应的适配器
        adapter = self._adapters.get(provider)
        if not adapter:
            raise ValueError(f"未支持的模型提供商: {provider}")

        # 2. 调用适配器的统一接口
        content = await adapter.generate_text(
            system_prompt=system_content,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )

        return system_content, content

_ai_nexus_instance = AINexus()

def get_ai_nexus() -> AINexus:
    return _ai_nexus_instance