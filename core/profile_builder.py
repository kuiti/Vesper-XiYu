"""从对话中提取长期用户画像"""

import json
import requests
from core.db import get_config, get_all_chat_messages

_profile_cache = None


def clear_profile_cache():
    """清除画像缓存，删除画像后调用"""
    global _profile_cache
    _profile_cache = None


def get_profile():
    """获取当前用户画像"""
    global _profile_cache
    if _profile_cache is not None:
        return _profile_cache
    from core.db import get_conn
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value, confidence FROM user_profile")
        rows = cursor.fetchall()
    _profile_cache = {r["key"]: {"value": r["value"], "confidence": r["confidence"]} for r in rows}
    return _profile_cache


def extract_profile_from_messages():
    """从最近对话批量提取用户画像信息"""
    api_key = get_config("api_key", "")
    if not api_key:
        return

    msgs = get_all_chat_messages()
    if not msgs or len(msgs) < 5:
        return

    recent = msgs[-100:]
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

    base_url = get_config("api_base_url", "https://api.deepseek.com/v1").rstrip("/")
    model = get_config("api_model", "deepseek-chat")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 300
    }
    try:
        resp = requests.post(f"{base_url}/chat/completions",
                             headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        for prefix in ["```json", "```"]:
            if raw.startswith(prefix):
                raw = raw[len(prefix):].strip()
        for suffix in ["```"]:
            if raw.endswith(suffix):
                raw = raw[:-len(suffix)].strip()
        data = json.loads(raw)
        save_profile(data)
    except Exception as e:
        print(f"[画像提取] 异常: {e}")


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
    _profile_cache = None


def get_profile_context():
    """生成画像上下文文本，用于注入 system prompt"""
    profile = get_profile()
    if not profile:
        return ""
    items = [f"{k}: {v['value']}" for k, v in profile.items()]
    return "【用户画像】\n" + "\n".join(items)
