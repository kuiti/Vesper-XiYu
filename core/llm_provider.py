# core/llm_provider.py — LLM Provider 抽象层
"""统一 LLM 接口，支持 DeepSeek / OpenAI / Ollama / Claude 等多种后端。

用法:
    provider = get_provider()
    for chunk in provider.chat_stream(messages, tools=tools):
        if chunk["type"] == "token":
            ...
        elif chunk["type"] == "tool_calls":
            ...
"""

from __future__ import annotations
import json
import time
import requests
from abc import ABC, abstractmethod
from typing import AsyncIterator, Iterator
from core.db import get_config


# ─── 抽象基类 ───

class LLMProvider(ABC):
    """LLM Provider 抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 唯一标识，如 'deepseek'、'openai'、'ollama'"""
        ...

    @abstractmethod
    def chat_stream(self, messages: list, **kwargs) -> Iterator[dict]:
        """流式聊天，每次 yield 一个 chunk dict。

        chunk 格式:
            {"type": "token", "data": "..."}        # 文本 token
            {"type": "tool_calls", "data": [...]}   # tool_calls 累积
            {"type": "done"}                         # 流结束
            {"type": "error", "data": "..."}         # 错误
        """
        ...

    @abstractmethod
    def chat(self, messages: list, **kwargs) -> str | None:
        """非流式聊天，返回完整文本或 None"""
        ...

    def get_headers(self) -> dict:
        """默认请求头"""
        return {"Content-Type": "application/json"}

    def get_base_url(self) -> str:
        """获取 API 基础 URL"""
        return (get_config("api_base_url", "") or "").rstrip("/")

    def get_model(self) -> str:
        """获取模型名称"""
        return get_config("api_model", "deepseek-chat")


# ─── OpenAI 兼容格式（DeepSeek / OpenAI / 任何 OpenAI 兼容 API）───

class OpenAICompatibleProvider(LLMProvider):
    """OpenAI 兼容格式的 Provider（DeepSeek、OpenAI、Together、Groq 等）"""

    @property
    def name(self) -> str:
        return get_config("llm_provider", "deepseek")

    def get_headers(self) -> dict:
        headers = super().get_headers()
        api_key = get_config("api_key", "")
        is_local = get_config("api_provider", "") == "ollama"
        if api_key and not is_local:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def chat_stream(self, messages: list, **kwargs) -> Iterator[dict]:
        api_key = get_config("api_key", "")
        is_local = get_config("api_provider", "") == "ollama"
        base_url = self.get_base_url() or "https://api.deepseek.com/v1"
        model = kwargs.pop("model", self.get_model())
        api_url = f"{base_url}/chat/completions"

        # 构建 payload（排除流式专属和内部参数）
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            **kwargs,
        }

        last_error = None
        for attempt in range(3):
            try:
                resp = requests.post(
                    api_url, headers=self.get_headers(), json=payload,
                    stream=True, timeout=kwargs.get("timeout", 90),
                )
                resp.raise_for_status()
                with resp:
                    tool_calls_buffer = {}
                    for line in resp.iter_lines():
                        if not line:
                            continue
                        line = line.decode("utf-8")
                        if not line.startswith("data: "):
                            continue
                        line = line[6:]
                        if line == "[DONE]":
                            if tool_calls_buffer:
                                yield {"type": "tool_calls", "data": list(tool_calls_buffer.values())}
                            yield {"type": "done"}
                            return
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        choices = chunk.get("choices", [])
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {})

                        # tool_calls
                        if "tool_calls" in delta:
                            for tc in delta["tool_calls"]:
                                idx = tc.get("index", 0)
                                if idx not in tool_calls_buffer:
                                    tool_calls_buffer[idx] = {"id": "", "function": {"name": "", "arguments": ""}}
                                if "id" in tc:
                                    tool_calls_buffer[idx]["id"] = tc["id"]
                                if "function" in tc:
                                    if "name" in tc["function"]:
                                        tool_calls_buffer[idx]["function"]["name"] = tc["function"]["name"]
                                    if "arguments" in tc["function"]:
                                        tool_calls_buffer[idx]["function"]["arguments"] += tc["function"]["arguments"]
                            continue

                        token = delta.get("content", "")
                        if token:
                            yield {"type": "token", "data": token}

                    # 流正常结束（无 [DONE] 标记）
                    if tool_calls_buffer:
                        yield {"type": "tool_calls", "data": list(tool_calls_buffer.values())}
                    yield {"type": "done"}
                    return

            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt < 2:
                    time.sleep(1 + attempt)
                continue

        yield {"type": "error", "data": str(last_error)}

    def chat(self, messages: list, **kwargs) -> str | None:
        api_key = get_config("api_key", "")
        is_local = get_config("api_provider", "") == "ollama"
        base_url = self.get_base_url() or "https://api.deepseek.com/v1"
        model = kwargs.pop("model", self.get_model())
        api_url = f"{base_url}/chat/completions"
        timeout = kwargs.pop("timeout", 60)

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            **kwargs,
        }

        last_error = None
        for attempt in range(3):
            try:
                resp = requests.post(
                    api_url, headers=self.get_headers(), json=payload, timeout=timeout,
                )
                resp.raise_for_status()
                body = resp.json()
                choices = body.get("choices", [])
                if not choices:
                    return None
                content = (choices[0].get("message", {}).get("content") or "").strip()
                return content or None
            except Exception as e:
                last_error = e
                if attempt < 2:
                    time.sleep(1 + attempt)
                continue

        print(f"[LLMProvider] {self.name} chat 失败: {last_error}")
        return None


# ─── Ollama Provider ───

class OllamaProvider(LLMProvider):
    """本地 Ollama"""

    @property
    def name(self) -> str:
        return "ollama"

    def get_base_url(self) -> str:
        return (get_config("api_base_url", "") or "http://localhost:11434").rstrip("/")

    def get_headers(self) -> dict:
        return {"Content-Type": "application/json"}

    def chat_stream(self, messages: list, **kwargs) -> Iterator[dict]:
        base_url = self.get_base_url()
        model = kwargs.pop("model", self.get_model())
        api_url = f"{base_url}/api/chat"

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            **kwargs,
        }

        try:
            resp = requests.post(
                api_url, headers=self.get_headers(), json=payload,
                stream=True, timeout=kwargs.get("timeout", 90),
            )
            resp.raise_for_status()
            with resp:
                for line in resp.iter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line.decode("utf-8"))
                    except json.JSONDecodeError:
                        continue
                    if chunk.get("done"):
                        yield {"type": "done"}
                        return
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield {"type": "token", "data": token}
            yield {"type": "done"}
        except Exception as e:
            yield {"type": "error", "data": str(e)}

    def chat(self, messages: list, **kwargs) -> str | None:
        base_url = self.get_base_url()
        model = kwargs.pop("model", self.get_model())
        api_url = f"{base_url}/api/chat"
        timeout = kwargs.pop("timeout", 60)

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            **kwargs,
        }

        try:
            resp = requests.post(
                api_url, headers=self.get_headers(), json=payload, timeout=timeout,
            )
            resp.raise_for_status()
            body = resp.json()
            return (body.get("message", {}).get("content") or "").strip() or None
        except Exception as e:
            print(f"[LLMProvider] ollama chat 失败: {e}")
            return None


# ─── 工厂函数 ───

_PROVIDER_CACHE = {}

def get_provider() -> LLMProvider:
    """工厂方法：根据 DB config 返回对应的 Provider 实例（带缓存）"""
    provider_name = get_config("llm_provider", "deepseek")

    if provider_name in _PROVIDER_CACHE:
        return _PROVIDER_CACHE[provider_name]

    mapping = {
        "deepseek": OpenAICompatibleProvider,
        "openai": OpenAICompatibleProvider,
        "ollama": OllamaProvider,
        "claude": OpenAICompatibleProvider,
    }

    cls = mapping.get(provider_name, OpenAICompatibleProvider)
    instance = cls()
    _PROVIDER_CACHE[provider_name] = instance
    return instance


def clear_provider_cache():
    """清除 Provider 缓存（切换模型后调用）"""
    _PROVIDER_CACHE.clear()


def get_available_providers() -> list[dict]:
    """返回可用 Provider 列表（给前端设置页用）"""
    return [
        {"id": "deepseek", "name": "DeepSeek", "desc": "DeepSeek 官方 API", "default_model": "deepseek-chat"},
        {"id": "openai", "name": "OpenAI", "desc": "OpenAI 兼容格式", "default_model": "gpt-4o"},
        {"id": "ollama", "name": "Ollama", "desc": "本地 Ollama", "default_model": "llama3"},
        {"id": "claude", "name": "Claude", "desc": "Anthropic Claude", "default_model": "claude-sonnet-4-6"},
    ]
