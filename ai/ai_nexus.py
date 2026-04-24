import asyncio
import json
import re
import threading
from dataclasses import dataclass
from typing import Optional

from loguru import logger
from ai.adapters.claude import ClaudeAdapter
from ai.adapters.claude_thinking import ClaudeThinkingAdapter
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


@dataclass
class _QueuedOllamaRequest:
    # Ollama 请求队列中的单个任务数据
    system_prompt: str
    user_prompt: str
    temperature: float
    max_tokens: Optional[int]
    context_messages: Optional[list[dict]]
    future: asyncio.Future

async def check_ai_input(prompt: str):
    # 检查输入长度是否超过系统限制
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
    # 统一过滤 AI 返回内容中的特定敏感词
    if not content:
        return ""

    # 如果发现包含敏感词，直接返回提示语
    if re.search(r"claude|anthropic", content, re.IGNORECASE):
        return "暂时无法生成，更改提示词试试。"

    return content


class AINexus:
    def __init__(self):
        # 预加载所有支持的适配器，减少运行时重复创建对象的开销
        self._adapters = {
            AIProvider.FREE: OllamaAdapter(),
            AIProvider.DEEPSEEK: DeepSeekAdapter(),
            AIProvider.DOUBAO: DoubaoAdapter(),
            AIProvider.DOUBAOPLUS: DoubaoPlusAdapter(),
            AIProvider.CLAUDE: ClaudeAdapter(),
            AIProvider.GEMINI: GeminiAdapter(),
            AIProvider.GPT: GPTAdapter(),
            AIProvider.ZHIPU: GLMAdapter(),
            AIProvider.CLAUDETHINKING: ClaudeThinkingAdapter(),
        }

        # Ollama 走异步队列，避免并发直接打到本地模型服务
        self._ollama_queue: asyncio.Queue[_QueuedOllamaRequest] | None = None
        self._ollama_worker_task: asyncio.Task | None = None
        self._ollama_worker_start_lock = threading.Lock()

    def _ensure_ollama_worker(self) -> None:
        # 确保 Ollama 队列和 worker 已初始化，且 worker 只启动一次
        with self._ollama_worker_start_lock:
            if self._ollama_queue is None:
                self._ollama_queue = asyncio.Queue()

            if self._ollama_worker_task is None or self._ollama_worker_task.done():
                self._ollama_worker_task = asyncio.create_task(self._ollama_queue_worker())

    async def _ollama_queue_worker(self) -> None:
        # 后台 worker：顺序处理 Ollama 请求，避免并发冲突
        assert self._ollama_queue is not None

        while True:
            request = await self._ollama_queue.get()
            try:
                ai_rsp = await self._adapters[AIProvider.FREE].generate_text(
                    system_prompt=request.system_prompt,
                    user_prompt=request.user_prompt,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                    context_messages=request.context_messages,
                )

                # 对返回内容做统一过滤
                try:
                    ai_rsp.content = filter_ai_content(ai_rsp.content)
                except Exception as e:
                    logger.error(f"AI内容过滤失败: {str(e)}", exc_info=True)

                if not request.future.done():
                    request.future.set_result(ai_rsp)
            except Exception as e:
                if not request.future.done():
                    request.future.set_exception(e)
            finally:
                self._ollama_queue.task_done()

    async def _generate_with_adapter(
        self,
        provider: AIProvider,
        adapter,
        user_prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int = None,
        context_messages: Optional[list[dict]] = None,
        enable_web_search: bool = False,
    ) -> AICompletionResponse:
        # 统一封装非 Ollama 模型的调用逻辑
        generate_kwargs = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "context_messages": context_messages,
        }

        if provider in {AIProvider.DOUBAO, AIProvider.DOUBAOPLUS}:
            generate_kwargs["enable_web_search"] = enable_web_search

        logger.info(f"[{provider.name}] temperature:{temperature} max_tokens:{max_tokens} web_search:{enable_web_search} begin to request....")
        ai_rsp = await adapter.generate_text(**generate_kwargs)

        # 对返回内容做统一过滤
        try:
            ai_rsp.content = filter_ai_content(ai_rsp.content)
        except Exception as e:
            logger.error(f"AI内容过滤失败: {str(e)}", exc_info=True)

        return ai_rsp

    async def _enqueue_ollama_request(
        self,
        user_prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int = None,
        context_messages: Optional[list[dict]] = None,
    ) -> AICompletionResponse:
        # 将 Ollama 请求放入队列，交由后台 worker 串行处理
        self._ensure_ollama_worker()
        assert self._ollama_queue is not None

        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        await self._ollama_queue.put(
            _QueuedOllamaRequest(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                context_messages=context_messages,
                future=future,
            )
        )
        return await future

    async def fill_context_with_adapter(self, provider: AIProvider, data: Optional[list[dict]] = None):
        # 兼容旧调用链，统一返回已标准化的上下文消息列表
        adapter = self._adapters.get(provider)
        if not adapter:
            raise ValueError(f"未支持的模型提供商: {provider}")

        normalized_messages = []
        for item in data or []:
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            content = item.get("content")
            if role not in {"user", "assistant"}:
                continue
            if not content:
                continue
            normalized_messages.append({"role": role, "content": content})

        return normalized_messages

    async def generate_novel_text(
        self,
        provider: AIProvider,
        user_prompt: str,
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = None,
        context_messages: Optional[list[dict]] = None,
        enable_web_search: bool = False,
    ) -> AICompletionResponse:
        # 根据 provider 选择对应适配器
        adapter = self._adapters.get(provider)
        if not adapter:
            raise ValueError(f"未支持的模型提供商: {provider}")

        # 限制温度范围，防止传入异常值
        safe_temperature = max(0.0, min(temperature, 1.2))

        # FREE 模型走队列，其他模型直接调用
        if provider == AIProvider.FREE:
            return await self._enqueue_ollama_request(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=safe_temperature,
                max_tokens=max_tokens,
                context_messages=context_messages,
            )

        return await self._generate_with_adapter(
            provider=provider,
            adapter=adapter,
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=safe_temperature,
            max_tokens=max_tokens,
            context_messages=context_messages,
            enable_web_search=enable_web_search,
        )

# 单例实例，避免重复创建 AINexus
_ai_nexus_instance = AINexus()

def get_ai_nexus() -> AINexus:
    # 对外提供统一入口
    return _ai_nexus_instance