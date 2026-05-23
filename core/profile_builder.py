"""从对话中提取长期用户画像"""

import json
import threading
from core.db import get_config, get_all_chat_messages

_profile_cache = None
_profile_cache_lock = threading.Lock()


def clear_profile_cache():
    """清除画像缓存，删除画像后调用"""
    global _profile_cache
    with _profile_cache_lock:
        _profile_cache = None


def get_profile():
    """获取当前用户画像"""
    global _profile_cache
    with _profile_cache_lock:
        if _profile_cache is not None:
            return dict(_profile_cache)
    from core.db import get_conn
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value, confidence FROM user_profile")
        rows = cursor.fetchall()
    cache = {r["key"]: {"value": r["value"], "confidence": r["confidence"]} for r in rows}
    with _profile_cache_lock:
        _profile_cache = cache
    return cache


def extract_profile_from_messages():
    """从最近对话批量提取用户画像信息"""
    api_key = get_config("api_key", "")
    if not api_key:
        return

    from core.db import get_recent_chat_messages
    recent = get_recent_chat_messages(100)
    if not recent or len(recent) < 5:
        return
    user_msgs = [m["content"] for m in recent if m.get("role") == "user"]
    if len(user_msgs) < 5:
        return

    existing = get_profile()
    existing_str = "\n".join([f"{k}: {v['value']}" for k, v in existing.items()]) if existing else "无"

    prompt = f"""从以下用户消息中提取用户信息。只输出 JSON，不要解释。
已有信息：{existing_str}
用户消息：
{chr(10).join(user_msgs[-30:])}

请提取：昵称/称呼、兴趣爱好、日常习惯、重要事件、其他备注。
格式：{{"key": "value", ...}}，只输出有把握的，不要猜测。"""

    from core.llm_client import call_llm
    data = call_llm(prompt=prompt, temperature=0.3, max_tokens=300, timeout=20, json_mode=True)
    if data and isinstance(data, dict):
        save_profile(data)


def save_profile(data: dict):
    """保存画像条目"""
    global _profile_cache
    from core.db import get_conn
    from datetime import datetime
    with get_conn() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        for key, value in data.items():
            cursor.execute(
                "REPLACE INTO user_profile (key, value, confidence, extracted_at) VALUES (?, ?, 1.0, ?)",
                (str(key), str(value), now)
            )
    with _profile_cache_lock:
        _profile_cache = None


def get_profile_context():
    """生成画像上下文文本，用于注入 system prompt"""
    profile = get_profile()
    if not profile:
        return ""
    items = [f"{k}: {v['value']}" for k, v in profile.items()]
    return "【用户画像】\n" + "\n".join(items)
