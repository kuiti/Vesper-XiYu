# core/db/memory.py  |  memory + user_profile + memory_history

from datetime import datetime
from . import get_conn


# ========== memory 操作 ==========
def get_memory():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM memory")
        rows = cursor.fetchall()
    return {row["key"]: row["value"] for row in rows}


def set_memory(key, value):
    with get_conn() as conn:
        cursor = conn.cursor()
        # 记忆审计日志
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


def delete_memory(key):
    with get_conn() as conn:
        cursor = conn.cursor()
        # 查询删除前的值用于审计
        cursor.execute("SELECT value FROM memory WHERE key = ?", (key,))
        old = cursor.fetchone()
        cursor.execute("DELETE FROM memory WHERE key = ?", (key,))
        if old:
            cursor.execute(
                "INSERT INTO memory_history (memory_key, old_value, new_value, event, created_at) VALUES (?, ?, ?, 'DELETE', ?)",
                (key, old["value"], None, datetime.now().isoformat())
            )