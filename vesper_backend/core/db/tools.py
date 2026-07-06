# core/db/tools.py  |  countdowns + presets + habits
"""工具类模块：习惯打卡、倒计时、预设管理。"""

import json
from datetime import datetime
from . import get_conn


# ========== habits ==========

def get_habits():
    """获取所有习惯"""
    with get_conn() as conn:
        rows = conn.cursor().execute("SELECT * FROM habits ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def add_habit(name: str):
    """添加习惯"""
    now = datetime.now().isoformat()
    today = datetime.now().strftime("%Y-%m-%d")
    with get_conn() as conn:
        conn.cursor().execute("INSERT INTO habits (name, date, created) VALUES (?, ?, ?)", (name, today, now))


def update_habit(habit_id: int, checked: bool, streak: int):
    """更新习惯状态"""
    today = datetime.now().strftime("%Y-%m-%d")
    with get_conn() as conn:
        conn.cursor().execute("UPDATE habits SET checked=?, streak=?, date=? WHERE id=?", (1 if checked else 0, streak, today, habit_id))


def delete_habit(habit_id: int) -> bool:
    """删除习惯"""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM habits WHERE id=?", (habit_id,))
        return c.rowcount > 0


def reset_habits_daily():
    """每日重置：未打卡的连续天数归零"""
    today = datetime.now().strftime("%Y-%m-%d")
    with get_conn() as conn:
        conn.cursor().execute(
            "UPDATE habits SET checked=0, streak=CASE WHEN date != ? THEN 0 ELSE streak END WHERE date != ?",
            (today, today)
        )


# ========== countdowns ==========

def get_countdowns():
    """获取所有倒计时项目。"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, target_date FROM countdowns")
        rows = cursor.fetchall()
    return [{"id": r["id"], "name": r["name"], "target": r["target_date"]} for r in rows]


def add_countdown(name, target_date):
    """添加一个倒计时。"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO countdowns (name, target_date) VALUES (?, ?)", (name, target_date))


def delete_countdown(cd_id):
    """删除指定倒计时。"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM countdowns WHERE id = ?", (cd_id,))


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