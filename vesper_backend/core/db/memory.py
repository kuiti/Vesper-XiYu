# core/db/memory.py  |  memory + user_profile + memory_history
"""记忆存储模块：键值记忆的增删改查，附带变更审计日志。
per-character：memory/user_profile/memory_history 表在角色库。
"""

from datetime import datetime
from . import get_chat_conn


# ========== memory 操作 ==========
def get_memory(character_id: int = 0):
    """获取所有键值记忆，返回字典（per-character）。"""
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM memory")
        rows = cursor.fetchall()
    return {row["key"]: row["value"] for row in rows}


def set_memory(key, value, character_id: int = 0):
    """写入或更新记忆，自动记录变更审计日志（per-character）。"""
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM memory WHERE key = ?", (key,))
        old = cursor.fetchone()
        if old and old["value"] != value:
            cursor.execute(
                "INSERT INTO memory_history (memory_key, old_value, new_value, event) VALUES (?, ?, ?, ?)",
                (key, old["value"], value, "UPDATE")
            )
        elif not old:
            cursor.execute(
                "INSERT INTO memory_history (memory_key, old_value, new_value, event) VALUES (?, ?, ?, ?)",
                (key, None, value, "CREATE")
            )
        cursor.execute("REPLACE INTO memory (key, value, updated_at) VALUES (?, ?, ?)", (key, value, datetime.now().isoformat()))


def delete_memory(key, character_id: int = 0):
    """删除指定记忆，自动记录删除审计日志（per-character）。"""
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM memory WHERE key = ?", (key,))
        old = cursor.fetchone()
        cursor.execute("DELETE FROM memory WHERE key = ?", (key,))
        if old:
            cursor.execute(
                "INSERT INTO memory_history (memory_key, old_value, new_value, event, created_at) VALUES (?, ?, ?, 'DELETE', ?)",
                (key, old["value"], None, datetime.now().isoformat())
            )