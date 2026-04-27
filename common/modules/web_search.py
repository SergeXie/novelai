import asyncio
import json
from typing import Any

import certifi
import requests
from loguru import logger

from common.config.config import settings


def _get_api_key() -> str:
    """获取联网搜索服务的 API Key。"""
    return settings.WEB_SEARCH_API_KEY.strip()


def _get_web_search_url() -> str:
    """获取联网搜索服务地址。"""
    return settings.WEB_SEARCH_URL.strip()


def _post_web_search(query: str, count: int = 5) -> requests.Response:
    """
    向联网搜索接口发送请求。

    参数:
    - query: 搜索关键词
    - count: 返回结果数量，限制在 1~10 之间

    返回:
    - requests.Response 对象
    """
    body = {
        "Query": query,
        "SearchType": "web_summary",
        "Count": max(1, min(count, 10)),
        "Filter": {
            # 不需要返回正文内容，只保留 URL
            "NeedContent": False,
            "NeedUrl": True,
        },
        # 需要服务端返回摘要
        "NeedSummary": True,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {_get_api_key()}",
    }
    return requests.post(
        _get_web_search_url(),
        headers=headers,
        json=body,
        timeout=30,
        # 使用 certifi 提供的证书链，避免本地证书环境差异
        verify=certifi.where(),
    )


def _try_parse_json(text: str) -> Any:
    """
    尝试将字符串解析为 JSON。

    解析失败时返回 None，而不是抛出异常。
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _get_dict_value(payload: dict[str, Any], *keys: str) -> Any:
    """
    从字典中按多个候选 key 获取值，忽略大小写。

    适用于第三方接口字段命名不稳定的情况。
    """
    if not isinstance(payload, dict):
        return None

    lowered = {str(key).lower(): value for key, value in payload.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value is not None:
            return value
    return None


def _parse_streaming_payload(response: requests.Response) -> list[Any]:
    """
    解析流式响应内容。

    兼容形如:
    - data: {...}
    - [DONE]

    的 SSE / 流式输出格式。
    """
    payloads: list[Any] = []
    for line in response.iter_lines():
        if not line:
            continue

        line_text = line.decode("utf-8", errors="ignore").strip()
        if not line_text:
            continue

        # 兼容 SSE 的 data: 前缀
        if line_text.startswith("data:"):
            line_text = line_text[5:].strip()

        # 流式结束标记，跳过
        if line_text == "[DONE]":
            continue

        parsed = _try_parse_json(line_text)
        if parsed is not None:
            payloads.append(parsed)

    return payloads


def _extract_summary(payload: Any) -> str:
    """
    从任意层级的返回结构中提取摘要文本。

    会优先尝试常见字段名，如:
    summary / answer / final_answer / content / text / snippet
    """
    if isinstance(payload, dict):
        # 先尝试直接从当前节点提取摘要
        for key in ("summary", "answer", "final_answer", "content", "text", "snippet"):
            value = _get_dict_value(payload, key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        # 再递归进入常见嵌套字段继续查找
        for key in ("data", "result", "results", "output", "webresults", "web_results"):
            value = _get_dict_value(payload, key)
            summary = _extract_summary(value)
            if summary:
                return summary

    if isinstance(payload, list):
        for item in payload:
            summary = _extract_summary(item)
            if summary:
                return summary

    return ""


def _extract_sources(payload: Any) -> list[dict[str, str]]:
    """
    从返回结果中递归提取来源信息。

    返回格式:
    [
        {
            "title": "...",
            "url": "...",
            "snippet": "..."
        }
    ]

    最终会按 URL 去重，并最多保留 5 条。
    """
    sources: list[dict[str, str]] = []

    def walk(node: Any) -> None:
        """递归遍历任意节点，收集可能的来源项。"""
        if isinstance(node, dict):
            title = _get_dict_value(node, "title", "name", "site_name", "siteName") or ""
            url = _get_dict_value(node, "url", "link", "source_url") or ""
            snippet = _get_dict_value(node, "snippet", "summary", "description", "text") or ""

            # 只要存在有效 URL，就认为这是一条来源记录
            if isinstance(url, str) and url.strip():
                sources.append(
                    {
                        "title": title.strip() if isinstance(title, str) else "",
                        "url": url.strip(),
                        "snippet": snippet.strip() if isinstance(snippet, str) else "",
                    }
                )

            # 继续递归遍历当前字典的所有值
            for value in node.values():
                walk(value)

        elif isinstance(node, list):
            # 遍历列表中的每个元素
            for item in node:
                walk(item)

    walk(payload)

    # 按 URL 去重，避免重复来源
    unique_sources: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for item in sources:
        url = item["url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)
        unique_sources.append(item)

    return unique_sources[:5]


def _build_context_from_payload(payload: Any) -> str:
    """
    将搜索结果构建为可注入到大模型提示词中的上下文文本。

    输出内容包含:
    - 搜索摘要
    - 参考来源列表
    """
    summary = _extract_summary(payload)
    sources = _extract_sources(payload)

    sections: list[str] = ["以下是当前问题的联网搜索结果，请优先基于这些最新资料回答，并在内容不确定时明确说明。"]

    if summary:
        sections.append(f"搜索摘要：\n{summary}")

    if sources:
        source_lines = []
        for index, item in enumerate(sources, start=1):
            line = f"{index}. {item['title'] or '未命名来源'} - {item['url']}"
            if item["snippet"]:
                line += f"\n   摘要：{item['snippet']}"
            source_lines.append(line)
        sections.append("参考来源：\n" + "\n".join(source_lines))

    # 如果只有提示语，没有任何实际搜索内容，则返回空字符串
    if len(sections) == 1:
        return ""

    return "\n\n".join(sections)


async def build_web_search_context(query: str, count: int = 5) -> str:
    """
    执行联网搜索，并将结果转换为上下文字符串。

    参数:
    - query: 搜索关键词
    - count: 期望返回的结果数量

    返回:
    - 可直接注入到提示词中的搜索上下文
    - 若搜索失败或无有效结果，则返回空字符串
    """
    # 空查询直接跳过
    if not query or not query.strip():
        return ""

    # 未配置 API Key 时不执行联网搜索
    if not _get_api_key():
        logger.warning("未配置联网搜索 API Key，跳过联网搜索")
        return ""

    # 未配置服务地址时不执行联网搜索
    if not _get_web_search_url():
        logger.warning("未配置联网搜索 URL，跳过联网搜索")
        return ""

    try:
        # requests 是同步库，这里放入线程池避免阻塞事件循环
        response = await asyncio.to_thread(_post_web_search, query.strip(), count)
        response.encoding = "utf-8"
        response.raise_for_status()
    except Exception as exc:
        logger.warning(f"联网搜索请求失败: {exc}")
        return ""

    # 优先按普通 JSON 响应解析
    payload = _try_parse_json(response.text)

    # 普通 JSON 解析失败时，再尝试按流式响应解析
    if payload is None:
        stream_payloads = _parse_streaming_payload(response)
        if not stream_payloads:
            logger.warning("联网搜索返回内容无法解析")
            return ""

        # 若流式返回有多段，优先保留最后结果；
        # 若只有一段，则直接使用该段
        payload = stream_payloads[-1] if len(stream_payloads) == 1 else stream_payloads

    # 构建最终上下文
    context = _build_context_from_payload(payload)
    if not context:
        logger.info("联网搜索未提取到可用摘要，跳过注入搜索上下文")
    return context