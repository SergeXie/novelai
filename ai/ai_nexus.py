import asyncio
import json
import re
import threading
from dataclasses import dataclass
from typing import Optional

from loguru import logger
from openai import AsyncOpenAI
from volcenginesdkarkruntime import Ark

from ai.adapters.base_adapter import OpenAIBaseAdapter
from ai.adapters.doubao import DoubaoAdapter
from ai.adapters.doubao_image import DoubaoImageAdapter
from ai.adapters.enums import AIProvider
from ai.adapters.mimo import MimoAdapter
from common.config.config import settings
from common.exception.lzsd_exception import ServiceWarning
from core.entity.vo.ai_response import AICompletionResponse


@dataclass
class _QueuedOllamaRequest:
    system_prompt: str
    user_prompt: str
    temperature: float
    max_tokens: Optional[int]
    context_messages: Optional[list[dict]]
    adapter: object
    future: asyncio.Future


async def check_ai_input(prompt: str):
    current_request_len = len(prompt)
    if current_request_len > settings.SINGLE_REQUEST_TOKEN_LIMIT:
        raise ServiceWarning(message="提示词过长")


def ai_clean_json(raw_text: str):
    """Extract JSON from an AI response that may contain prose or markdown fences."""
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        raise ValueError("AI 返回内容中未检测到 JSON 结构")

    json_str = match.group(0)
    if "'" in json_str and '"' not in json_str:
        json_str = json_str.replace("'", '"')

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as exc:
        fixed_json = re.sub(r",\s*([\]}])", r"\1", json_str)
        try:
            return json.loads(fixed_json)
        except json.JSONDecodeError:
            raise ValueError(f"JSON 解析最终失败: {exc}") from exc


def filter_ai_content(content: str) -> str:
    if not content:
        return ""

    if re.search(r"claude|anthropic", content, re.IGNORECASE):
        return "暂时无法生成，请更改提示词重试。"

    return content


class AINexus:
    def __init__(self):
        # Text adapters are built from mc_ai_models for each request.
        self._image_adapters = {}
        self._ollama_queue: asyncio.Queue[_QueuedOllamaRequest] | None = None
        self._ollama_worker_task: asyncio.Task | None = None
        self._ollama_worker_start_lock = threading.Lock()

    def _ensure_ollama_worker(self) -> None:
        with self._ollama_worker_start_lock:
            if self._ollama_queue is None:
                self._ollama_queue = asyncio.Queue()

            if self._ollama_worker_task is None or self._ollama_worker_task.done():
                self._ollama_worker_task = asyncio.create_task(self._ollama_queue_worker())

    async def _ollama_queue_worker(self) -> None:
        assert self._ollama_queue is not None

        while True:
            request = await self._ollama_queue.get()
            try:
                ai_rsp = await request.adapter.generate_text(
                    system_prompt=request.system_prompt,
                    user_prompt=request.user_prompt,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                    context_messages=request.context_messages,
                )
                ai_rsp.content = filter_ai_content(ai_rsp.content)

                if not request.future.done():
                    request.future.set_result(ai_rsp)
            except Exception as exc:
                if not request.future.done():
                    request.future.set_exception(exc)
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
        logger.info(
            f"[{provider.name}] temperature:{temperature} max_tokens:{max_tokens} "
            f"web_search:{enable_web_search} begin to request...."
        )
        ai_rsp = await adapter.generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            context_messages=context_messages,
            enable_web_search=enable_web_search,
        )
        ai_rsp.content = filter_ai_content(ai_rsp.content)
        return ai_rsp

    async def _enqueue_ollama_request(
        self,
        adapter,
        user_prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int = None,
        context_messages: Optional[list[dict]] = None,
    ) -> AICompletionResponse:
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
                adapter=adapter,
                future=future,
            )
        )
        return await future

    async def fill_context_with_adapter(self, provider: AIProvider, data: Optional[list[dict]] = None):
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

    def _get_image_adapter(self, provider: AIProvider):
        if provider not in self._image_adapters:
            if provider != AIProvider.DOUBAOIMAGE:
                raise ValueError(f"暂不支持该图片模型: {provider}")
            self._image_adapters[provider] = DoubaoImageAdapter()
        return self._image_adapters[provider]

    @staticmethod
    def _get_model_value(model_config, key: str, default=None):
        if model_config is None:
            return default
        if isinstance(model_config, dict):
            return model_config.get(key, default)
        return getattr(model_config, key, default)

    def _build_adapter_from_model_config(self, provider: AIProvider, model_config):
        model_name = self._get_model_value(model_config, "model_identifier")
        api_key = self._get_model_value(model_config, "api_key")
        base_url = self._get_model_value(model_config, "base_url")
        max_tokens = int(self._get_model_value(model_config, "max_tokens", 4096) or 4096)
        temperature = float(self._get_model_value(model_config, "temperature", 0.7) or 0.7)
        display_name = self._get_model_value(model_config, "model_name", provider.name)

        if not model_name or not base_url:
            raise ValueError(f"模型配置不完整 level={self._get_model_value(model_config, 'level')}")

        provider_name = str(self._get_model_value(model_config, "provider", provider.name)).lower()
        adapter_name = f"{display_name}/{provider_name}"

        if provider in (AIProvider.DOUBAO, AIProvider.DOUBAOPLUS) or provider_name == "doubao":
            adapter = DoubaoAdapter.__new__(DoubaoAdapter)
            adapter.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            adapter.ark_client = Ark(base_url=base_url, api_key=api_key)
            adapter.tools = [{"type": "web_search", "max_keyword": 2}]
        elif provider == AIProvider.MIMO or provider_name == "mimo":
            adapter = MimoAdapter.__new__(MimoAdapter)
            adapter.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        else:
            adapter = OpenAIBaseAdapter(
                name=adapter_name,
                api_key=api_key,
                base_url=base_url,
                model_name=model_name,
                max_tokens=max_tokens,
                temperature=temperature,
            )

        adapter.name = adapter_name
        adapter.model_name = model_name
        adapter.max_tokens = max_tokens
        adapter.temperature = temperature
        return adapter

    @staticmethod
    def _legacy_model_config(provider: AIProvider) -> dict | None:
        config_map = {
            AIProvider.FREE: settings.free,
            AIProvider.DEEPSEEK: settings.deepseek,
            AIProvider.DOUBAO: settings.doubao,
            AIProvider.DOUBAOPLUS: settings.doubaoplus,
            AIProvider.CLAUDE: settings.claude,
            AIProvider.GEMINI: settings.gemini,
            AIProvider.GPT: settings.gpt,
            AIProvider.ZHIPU: settings.zhipu,
            AIProvider.CLAUDETHINKING: settings.claudethinking,
            AIProvider.MIMO: settings.mimo,
        }
        cfg = config_map.get(provider)
        if not cfg or not cfg.model_name or not cfg.base_url:
            return None
        return {
            "level": provider.value,
            "model_name": cfg.model_name,
            "model_identifier": cfg.model_name,
            "provider": provider.name,
            "multiplier": cfg.multiplier,
            "max_tokens": cfg.max_tokens,
            "temperature": cfg.temperature,
            "context_window": cfg.max_tokens,
            "base_url": cfg.base_url,
            "api_key": cfg.api_key,
        }

    async def generate_image(
        self,
        prompt: str,
        provider: AIProvider = AIProvider.DOUBAOIMAGE,
        size: str = "2K",
        n: int = 1,
        watermark: bool = False,
        response_format: str = "url",
        extra_body: Optional[dict] = None,
    ) -> str:
        adapter = self._get_image_adapter(provider)
        return await adapter.generate_image(
            prompt=prompt,
            size=size,
            n=n,
            watermark=watermark,
            response_format=response_format,
            extra_body=extra_body,
        )

    async def generate_novel_text(
        self,
        provider: AIProvider,
        user_prompt: str,
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = None,
        context_messages: Optional[list[dict]] = None,
        enable_web_search: bool = False,
        model_config=None,
    ) -> AICompletionResponse:
        if not model_config:
            model_config = self._legacy_model_config(provider)
        if not model_config:
            raise ValueError(f"缺少数据库模型配置: {provider}")

        adapter = self._build_adapter_from_model_config(provider, model_config)
        safe_temperature = max(0.0, min(float(temperature), 1.2))

        if provider == AIProvider.FREE:
            return await self._enqueue_ollama_request(
                adapter=adapter,
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


_ai_nexus_instance = AINexus()


def get_ai_nexus() -> AINexus:
    return _ai_nexus_instance
