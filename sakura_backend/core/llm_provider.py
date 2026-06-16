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
import random
import requests
from abc import ABC, abstractmethod
from typing import Iterator
from core.db import get_config


# ─── 重试工具函数 ───

def _exponential_backoff(attempt: int, base: float = 1.0, max_delay: float = 30.0) -> float:
    """指数退避 + 随机抖动，返回等待秒数"""
    delay = min(base * (2 ** attempt), max_delay)
    jitter = random.uniform(0, delay * 0.25)
    return delay + jitter


def _is_retryable_error(e: Exception) -> bool:
    """判断错误是否值得重试"""
    err_str = str(e).lower()
    # 非重试类：鉴权、模型不存在、内容审查、参数错误
    non_retryable = [
        "401", "402", "403",  # 鉴权/计费
        "invalid_api_key", "auth", "unauthorized",
        "model_not_found", "model not found",
        "content_filter", "content_policy",
        "invalid_request_error", "bad_request",
    ]
    for keyword in non_retryable:
        if keyword in err_str:
            return False
    # 重试类：超时、限流、服务端错误、网络错误
    return True


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

    # 最后成功回复缓存（API 全挂时当 fallback）
    _last_successful_reply = ""

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

    def _build_payload(self, messages: list, stream: bool, **kwargs) -> dict:
        """构建请求 payload（排除内部参数）"""
        return {
            "model": kwargs.pop("model", self.get_model()),
            "messages": messages,
            "stream": stream,
            **kwargs,
        }

    def chat_stream(self, messages: list, **kwargs) -> Iterator[dict]:
        api_key = get_config("api_key", "")
        is_local = get_config("api_provider", "") == "ollama"
        base_url = self.get_base_url() or "https://api.deepseek.com/v1"
        api_url = f"{base_url}/chat/completions"
        timeout = kwargs.pop("stream_timeout", kwargs.pop("timeout", 90))

        # 模型回退链：主模型 → 备选模型
        main_model = kwargs.pop("model", self.get_model())
        models_to_try = [main_model]
        fallback_models_raw = get_config("fallback_models", "")
        if fallback_models_raw and not is_local:
            models_to_try.extend([m.strip() for m in fallback_models_raw.split(",") if m.strip() and m.strip() != main_model])

        payload = self._build_payload(messages, stream=True, model=models_to_try[0], **kwargs)
        last_error = None

        for model_idx, current_model in enumerate(models_to_try):
            payload["model"] = current_model
            for attempt in range(3):
                try:
                    resp = requests.post(
                        api_url, headers=self.get_headers(), json=payload,
                        stream=True, timeout=timeout,
                    )
                    resp.raise_for_status()
                    if model_idx > 0 or attempt > 0:
                        print(f"[LLMProvider] 流式恢复: 模型={current_model}, 尝试#{attempt+1}")
                    full_text = ""
                    with resp:
                        tool_calls_buffer = {}
                        try:
                            for line in resp.iter_lines():
                                if not line:
                                    continue
                                line = line.decode("utf-8")
                                if not line.startswith("data: "):
                                    continue
                                line = line[6:]
                                if line == "[DONE]":
                                    if full_text:
                                        self._last_successful_reply = full_text
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
                                    full_text += token
                                    yield {"type": "token", "data": token}
                        except GeneratorExit:
                            return

                        # 流正常结束（无 [DONE] 标记）
                        if full_text:
                            self._last_successful_reply = full_text
                        if tool_calls_buffer:
                            yield {"type": "tool_calls", "data": list(tool_calls_buffer.values())}
                        yield {"type": "done"}
                        return

                except requests.exceptions.RequestException as e:
                    last_error = e
                    if not _is_retryable_error(e):
                        print(f"[LLMProvider] 非重试错误，放弃: {e}")
                        yield {"type": "error", "data": str(e)}
                        return
                    if attempt < 2:
                        delay = _exponential_backoff(attempt)
                        print(f"[LLMProvider] 重试 #{attempt+1} ({current_model})，{delay:.1f}s: {e}")
                        time.sleep(delay)
                    continue

            # 当前模型重试用尽，切下一个
            if model_idx < len(models_to_try) - 1:
                print(f"[LLMProvider] 切备选模型: {current_model} → {models_to_try[model_idx+1]}")
                time.sleep(1)

        yield {"type": "error", "data": str(last_error) if last_error else "所有模型均失败"}

    def get_last_successful_reply(self) -> str:
        """获取上次成功回复（API 全挂时当 fallback 文本）"""
        return self._last_successful_reply

    def chat(self, messages: list, **kwargs) -> str | None:
        api_key = get_config("api_key", "")
        is_local = get_config("api_provider", "") == "ollama"
        base_url = self.get_base_url() or "https://api.deepseek.com/v1"
        api_url = f"{base_url}/chat/completions"
        timeout = kwargs.pop("timeout", 60)

        main_model = kwargs.pop("model", self.get_model())
        models_to_try = [main_model]
        fallback_models_raw = get_config("fallback_models", "")
        if fallback_models_raw and not is_local:
            models_to_try.extend([m.strip() for m in fallback_models_raw.split(",") if m.strip() and m.strip() != main_model])

        payload = self._build_payload(messages, stream=False, model=models_to_try[0], **kwargs)
        last_error = None

        for model_idx, current_model in enumerate(models_to_try):
            payload["model"] = current_model
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
                    if content:
                        self._last_successful_reply = content
                    return content or None
                except Exception as e:
                    last_error = e
                    if not _is_retryable_error(e):
                        print(f"[LLMProvider] 非重试错误，放弃: {e}")
                        return None
                    if attempt < 2:
                        delay = _exponential_backoff(attempt)
                        print(f"[LLMProvider] 非流式重试 #{attempt+1} ({current_model})，{delay:.1f}s: {e}")
                        time.sleep(delay)
                    continue

            if model_idx < len(models_to_try) - 1:
                print(f"[LLMProvider] 非流式切备选模型: {current_model} → {models_to_try[model_idx+1]}")
                time.sleep(1)

        print(f"[LLMProvider] {self.name} chat 全部失败: {last_error}")
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

    # 最后成功回复缓存
    _last_successful_reply = ""

    def chat_stream(self, messages: list, **kwargs) -> Iterator[dict]:
        base_url = self.get_base_url()
        model = kwargs.pop("model", self.get_model())
        api_url = f"{base_url}/api/chat"
        timeout = kwargs.pop("stream_timeout", kwargs.pop("timeout", 90))

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
                    stream=True, timeout=timeout,
                )
                resp.raise_for_status()
                full_text = ""
                with resp:
                    for line in resp.iter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line.decode("utf-8"))
                        except json.JSONDecodeError:
                            continue
                        if chunk.get("done"):
                            if full_text:
                                self._last_successful_reply = full_text
                            yield {"type": "done"}
                            return
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            full_text += token
                            yield {"type": "token", "data": token}
                if full_text:
                    self._last_successful_reply = full_text
                yield {"type": "done"}
                return
            except Exception as e:
                last_error = e
                if attempt < 2:
                    delay = _exponential_backoff(attempt)
                    print(f"[LLMProvider] Ollama 重试 #{attempt+1}，{delay:.1f}s: {e}")
                    time.sleep(delay)
                continue

        yield {"type": "error", "data": str(last_error) if last_error else "Ollama 连接失败"}

    def get_last_successful_reply(self) -> str:
        return self._last_successful_reply

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

        last_error = None
        for attempt in range(3):
            try:
                resp = requests.post(
                    api_url, headers=self.get_headers(), json=payload, timeout=timeout,
                )
                resp.raise_for_status()
                body = resp.json()
                return (body.get("message", {}).get("content") or "").strip() or None
            except Exception as e:
                last_error = e
                if not _is_retryable_error(e):
                    print(f"[LLMProvider] ollama 非重试错误: {e}")
                    return None
                if attempt < 2:
                    delay = _exponential_backoff(attempt)
                    print(f"[LLMProvider] ollama 重试 #{attempt+1}，{delay:.1f}s: {e}")
                    time.sleep(delay)

        print(f"[LLMProvider] ollama chat 全部失败: {last_error}")
        return None


# ─── 工厂函数 ───

import threading

_PROVIDER_CACHE = {}
_PROVIDER_CACHE_LOCK = threading.Lock()

def get_provider() -> LLMProvider:
    """工厂方法：根据 DB config 返回对应的 Provider 实例（带缓存，线程安全）"""
    provider_name = get_config("llm_provider", "deepseek")

    # 快速路径：缓存命中
    if provider_name in _PROVIDER_CACHE:
        return _PROVIDER_CACHE[provider_name]

    # 慢路径：创建新实例
    with _PROVIDER_CACHE_LOCK:
        # 双重检查
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
    with _PROVIDER_CACHE_LOCK:
        _PROVIDER_CACHE.clear()


def get_available_providers() -> list[dict]:
    """返回可用 Provider 列表（给前端设置页用）"""
    return [
        {"id": "deepseek", "name": "DeepSeek", "desc": "DeepSeek 官方 API", "default_model": "deepseek-chat"},
        {"id": "openai", "name": "OpenAI", "desc": "OpenAI 兼容格式", "default_model": "gpt-4o"},
        {"id": "ollama", "name": "Ollama", "desc": "本地 Ollama", "default_model": "llama3"},
        {"id": "claude", "name": "Claude", "desc": "Anthropic Claude", "default_model": "claude-sonnet-4-6"},
    ]
