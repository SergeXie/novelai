import json
import re

from loguru import logger
from ai.adapters.claude import ClaudeAdapter
from ai.adapters.deep_seek import DeepSeekAdapter
from ai.adapters.doubao import DoubaoAdapter
from ai.adapters.doubao_plus import DoubaoPlusAdapter
from ai.adapters.enums import AIProvider
from ai.adapters.gpt import GPTAdapter
from ai.adapters.ollama import OllamaAdapter
from ai.adapters.gemini import GeminiAdapter
from ai.adapters.glm import GLMAdapter
from common.config.config import settings
from common.exception.lzsd_exception import ServiceWarning
from core.entity.vo.ai_response import AICompletionResponse

async def check_ai_input(prompt:str):
    current_request_len = len(prompt)
    if current_request_len > settings.SINGLE_REQUEST_TOKEN_LIMIT:
        raise ServiceWarning(message="提示词过长")

def ai_clean_json(raw_text: str):
    """
    专门处理 AI 返回的带废话、带元组包装或 Markdown 代码块的 JSON
    """
    # 1. 尝试直接解析（最快路径）
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    # 2. 提取最外层的 { ... }
    # 使用 re.DOTALL 确保匹配换行符
    match = re.search(r'\{.*\}', raw_text, re.DOTALL)
    if not match:
        raise ValueError("AI 返回内容中未检测到 JSON 结构")

    json_str = match.group(0)

    # 3. 处理特殊的单引号问题（AI 有时会输出 Python 风格的单引号 JSON）
    # 注意：这只是简单的启发式替换，复杂的转义可能需要更精细的处理
    if "'" in json_str and '"' not in json_str:
        json_str = json_str.replace("'", '"')

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        # 4. 最后尝试修复常见的尾部逗号
        try:
            fixed_json = re.sub(r',\s*([\]}])', r'\1', json_str)
            return json.loads(fixed_json)
        except:
            raise ValueError(f"JSON 解析最终失败: {str(e)}")

def filter_ai_content(content: str) -> str:
    if not content:
        return ""

    # 匹配 "claude" 或 "anthropic"（忽略大小写）
    # 如果发现包含敏感词，直接返回空字符串
    if re.search(r"claude|anthropic", content, re.IGNORECASE):
        return "暂时无法生成，更改提示词试试。"

    return content


class AINexus:
    def __init__(self):
        # 预加载所有支持的适配器
        self._adapters = {
            AIProvider.FREE: OllamaAdapter(),
            AIProvider.DEEPSEEK: DeepSeekAdapter(),
            AIProvider.DOUBAO: DoubaoAdapter(),
            AIProvider.DOUBAOPLUS: DoubaoPlusAdapter(),
            AIProvider.CLAUDE: ClaudeAdapter(),
            AIProvider.GEMINI: GeminiAdapter(),
            AIProvider.GPT: GPTAdapter(),
            AIProvider.ZHIPU: GLMAdapter(),
        }

    async def generate_novel_text(self, provider: AIProvider, user_prompt: str, system_prompt:str, temperature:float = 0.7, max_tokens: int = None) \
            -> AICompletionResponse:

        # 1. 根据传入的 provider 获取对应的适配器
        adapter = self._adapters.get(provider)
        if not adapter:
            raise ValueError(f"未支持的模型提供商: {provider}")

        safe_temperature = max(0.0, min(temperature, 1.2))

        # 2. 调用适配器的统一接口
        ai_rsp = await adapter.generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=safe_temperature
        )
        try:
            ai_rsp.content = filter_ai_content(ai_rsp.content)
        except Exception as e:
            logger.error(f"AI内容过滤失败: {str(e)}", exc_info=True)

        return ai_rsp

_ai_nexus_instance = AINexus()

def get_ai_nexus() -> AINexus:
    return _ai_nexus_instance