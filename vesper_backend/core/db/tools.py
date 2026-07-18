# core/db/tools.py  |  presets
"""工具类模块：预设管理。"""

import json
from datetime import datetime
from . import get_conn


# ========== presets ==========
# 预设中的敏感键，保存/加载时静默过滤以保护 API 密钥不泄露
_SENSITIVE_KEYS = {"api_key", "amap_key"}


def get_presets():
    """获取所有预设，自动过滤敏感键（如 API 密钥）。"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, data FROM presets")
        rows = cursor.fetchall()
    result = {}
    for r in rows:
        try:
            d = json.loads(r["data"])
        except (json.JSONDecodeError, TypeError):
            continue
        for k in _SENSITIVE_KEYS:
            d.pop(k, None)
        result[r["name"]] = d
    return result


def save_preset(name, data):
    """保存预设，自动过滤敏感键。"""
    clean = {k: v for k, v in data.items() if k not in _SENSITIVE_KEYS}
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("REPLACE INTO presets (name, data) VALUES (?, ?)",
                       (name, json.dumps(clean, ensure_ascii=False)))


def delete_preset(name):
    """删除指定预设。"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM presets WHERE name = ?", (name,))