# core/memory_utils.py — 记忆筛选工具
"""记忆筛选工具：提供安全的记忆条目检索和用户偏好提取功能。"""

from core.db import get_conn
import random


def get_safe_memories(limit: int = 3) -> list:
    """筛选高置信度、非敏感的 memory 条目，返回内容列表。
    排除明显是敏感信息的 key（密码、密钥、token、身份证号等）。
    """
    sensitive_patterns = [
        "密码", "password", "密钥", "secret", "token", "api_key",
        "身份证", "银行卡", "手机号", "地址", "电话", "email", "邮箱",
        "账号", "账户", "pass", "credential", "private",
    ]

    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT key, value FROM memory ORDER BY updated_at DESC LIMIT 200"
        )
        rows = [dict(r) for r in cursor.fetchall()]

    candidates = []
    for r in rows:
        key = r["key"].lower()
        if any(p in key for p in sensitive_patterns):
            continue
        value = r["value"]
        if not value or not isinstance(value, str):
            continue
        if len(value) < 2 or len(value) > 200:
            continue
        candidates.append({"key": r["key"], "value": value})

    if len(candidates) <= limit:
        return candidates

    return random.sample(candidates, limit)


def get_user_preferences() -> list:
    """从 user_profile 表提取偏好类信息（喜欢/不喜欢/习惯）"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT key, value FROM user_profile WHERE confidence >= 0.5 ORDER BY extracted_at DESC LIMIT 20"
        )
        rows = [dict(r) for r in cursor.fetchall()]

    prefs = []
    pref_keywords = ["喜欢", "不喜欢", "爱好", "习惯", "讨厌", "偏好", "经常"]
    for r in rows:
        key = r.get("key", "")
        value = r.get("value", "")
        combined = f"{key}: {value}"
        if any(kw in combined for kw in pref_keywords):
            prefs.append(combined)
    return prefs
