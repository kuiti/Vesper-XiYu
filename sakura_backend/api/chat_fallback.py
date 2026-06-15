# api/chat_fallback.py — 三阶段降级逻辑（从 api/chat.py 提取）
"""
Stage 1: 非流式重试（不用 tool，纯文本生成）
Stage 2: 缓存兜底
Stage 3: 错误消息
"""
import asyncio
import json
import logging
from datetime import datetime
from core.db import add_chat_message
from api.split_sentences import fallback_split
from api.chat_tasks import _clean_dsml

logger = logging.getLogger(__name__)


async def try_fallback_reply(
    websocket,  # WebSocket 实例
    messages: list,  # LLM messages
    full_reply: list,  # 已收到的 token 列表
    assistant_content: str,  # 当前 assistant 内容
    _is_system: bool,
    _stream_error: Exception,
):
    """
    三阶段降级。返回 (handled, new_full_reply, new_assistant_content)
    - handled=True: 已处理（websocket 已发送 token/done/error），调用方应 continue
    - handled=False: 降级也失败，调用方继续发 error
    """
    # Stage 1: 非流式重试
    try:
        from core.llm_provider import get_provider
        fallback_provider = get_provider()
        fallback_msgs = [m for m in messages if m["role"] != "system"]
        fallback_reply = fallback_provider.chat(
            fallback_msgs,
            temperature=0.5,
            max_tokens=500,
        )
        if fallback_reply:
            cleaned = _clean_dsml(fallback_reply)
            sentences = fallback_split(cleaned)
            if sentences:
                for sentence in sentences:
                    add_chat_message("assistant", _clean_dsml(sentence))
            else:
                add_chat_message("assistant", cleaned)
            for char in cleaned:
                await websocket.send_text(json.dumps({"type": "token", "content": char}))
                await asyncio.sleep(0.02)
            await websocket.send_text(json.dumps({"type": "done"}))
            logger.info("[降级] 非流式降级成功")
            return True, [cleaned], cleaned
    except Exception as e2:
        logger.warning(f"[降级] 非流式也失败: {e2}")

    # Stage 2: 缓存兜底
    try:
        _cached = fallback_provider.get_last_successful_reply()
    except Exception:
        _cached = ""
    if _cached:
        logger.info(f"[降级] 使用缓存回复 ({len(_cached)} chars)")
        _brief = _cached[:200] + "……（刚才的回复有点问题，这是上次的内容）"
        await websocket.send_text(json.dumps({"type": "token", "content": _brief}))
        await websocket.send_text(json.dumps({"type": "done"}))
        return True, [_brief], _brief

    # Stage 3: 错误消息
    err_msg = "生成回复失败，请稍后重试" if full_reply else "AI 服务请求失败，请稍后重试"
    await websocket.send_text(json.dumps({"type": "error", "content": err_msg}))
    return True, [], ""