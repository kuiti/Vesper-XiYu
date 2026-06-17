# core/llm_client.py — 统一 LLM API 调用入口
"""消除 8 个文件中重复的 HTTP 样板代码。所有非流式 LLM 调用统一走此模块。"""
import json
import re
import time
import logging
from core.llm_provider import get_provider

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> str | None:
    """从文本中提取第一个完整 JSON 对象/数组（支持任意嵌套深度）"""
    for i, ch in enumerate(text):
        if ch not in ('{', '['):
            continue
        opener, closer = ('{', '}') if ch == '{' else ('[', ']')
        depth = 0
        in_string = False
        escape = False
        for j in range(i, len(text)):
            c = text[j]
            if escape:
                escape = False
                continue
            if c == '\\' and in_string:
                escape = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == opener:
                depth += 1
            elif c == closer:
                depth -= 1
                if depth == 0:
                    return text[i:j+1]
    return None


def call_llm(
    prompt: str,
    system: str = None,
    temperature: float = 0.3,
    max_tokens: int = 300,
    timeout: int = 15,
    json_mode: bool = False,
) -> str | dict | None:
    """调用 LLM API，返回响应内容（使用 LLMProvider 抽象层）。

    Args:
        prompt: 用户消息（放在 user role）
        system: 可选 system message
        temperature: 温度 0-1
        max_tokens: 最大输出 token
        timeout: 请求超时秒数
        json_mode: 是否自动去 markdown fence 并 json.loads()

    Returns:
        json_mode=False: str | None（去首尾空白后的文本）
        json_mode=True:  dict | None（解析后的 JSON）
        API key 未配置或调用失败: None
    """
    provider = get_provider()
    # 快速检查 provider 是否可用
    from core.db import get_config
    api_key = get_config("api_key", "")
    is_local = get_config("api_provider", "") == "ollama"
    if not api_key and not is_local and provider.name not in ("ollama",):
        logger.warning("[LLM] API Key 未配置")
        return None

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    # 调用 provider.chat()（provider 内部已有重试逻辑）
    content = None
    try:
        content = provider.chat(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
    except Exception as e:
        logger.error("[LLM] 调用失败: %s", e)

    if not content:
        return None

    if not json_mode:
        return content

    # ─── JSON 模式：去 markdown fence + 解析 ───
    # 在全文查找 ```json ... ``` 代码块
    fence_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
    if fence_match:
        content = fence_match.group(1).strip()

    # 去首尾残留 fence 标记
    for prefix in ["```json", "```"]:
        if content.startswith(prefix):
            content = content[len(prefix):].strip()
    for suffix in ["```"]:
        if content.endswith(suffix):
            content = content[:-len(suffix)].strip()

    # 若仍未以 { 或 [ 开头，用括号匹配提取（支持任意嵌套深度）
    if not (content.startswith("{") or content.startswith("[")):
        content = _extract_json(content) or content

    try:
        return json.loads(content)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"[LLM] JSON 解析失败: {e} | content={content[:200]}")
        return None
