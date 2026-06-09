# core/db/chat.py  |  chat_history + FTS 触发器

import json
from datetime import datetime, timedelta
from . import get_conn


# ========== chat_history ==========
def get_all_chat_messages():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT role, content, timestamp FROM chat_history ORDER BY id")
        rows = cursor.fetchall()
    return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]


def get_recent_chat_messages(limit: int = 100):
    """获取最近 N 条消息（倒序查询后反转，保证时间正序）"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT role, content, timestamp FROM chat_history ORDER BY id DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
    return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in reversed(rows)]


def get_last_user_messages(n=3):
    """获取最近 n 条用户消息（按时间倒序）"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content, timestamp FROM chat_history WHERE role='user' ORDER BY id DESC LIMIT ?",
            (n,)
        )
        rows = cursor.fetchall()
    return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]


def add_chat_message(role, content, timestamp=None):
    if timestamp is None:
        timestamp = datetime.now().isoformat()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO chat_history (role, content, timestamp) VALUES (?, ?, ?)",
                       (role, content, timestamp))
        return cursor.lastrowid


def delete_chat_history_older_than(days: int):
    with get_conn() as conn:
        cursor = conn.cursor()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cursor.execute("SELECT id FROM chat_history WHERE timestamp < ?", (cutoff,))
        ids = [row["id"] for row in cursor.fetchall()]
        if ids:
            placeholders = ','.join('?' for _ in ids)
            cursor.execute(f"DELETE FROM chat_fts WHERE rowid IN ({placeholders})", ids)
            cursor.execute(f"DELETE FROM sentence_index WHERE msg_id IN ({placeholders})", ids)
            cursor.execute(f"DELETE FROM favorites WHERE msg_id IN ({placeholders})", ids)
            cursor.execute(f"DELETE FROM empathy_feedback WHERE msg_id IN ({placeholders})", ids)
            cursor.execute("DELETE FROM chat_history WHERE timestamp < ?", (cutoff,))
            cursor.execute("UPDATE summary_msg_counter SET count = MAX(0, count - ?), last_level1_at = MIN(last_level1_at, MAX(0, count - ?)), last_level2_at = MIN(last_level2_at, MAX(0, count - ?)), last_level3_at = MIN(last_level3_at, MAX(0, count - ?)) WHERE id = 1", (len(ids), len(ids), len(ids), len(ids)))


def delete_chat_history_between(start_iso: str, end_iso: str):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM chat_history WHERE timestamp BETWEEN ? AND ?", (start_iso, end_iso))
        ids = [row["id"] for row in cursor.fetchall()]
        if ids:
            placeholders = ','.join('?' for _ in ids)
            cursor.execute(f"DELETE FROM chat_fts WHERE rowid IN ({placeholders})", ids)
            cursor.execute(f"DELETE FROM sentence_index WHERE msg_id IN ({placeholders})", ids)
            cursor.execute(f"DELETE FROM favorites WHERE msg_id IN ({placeholders})", ids)
            cursor.execute(f"DELETE FROM empathy_feedback WHERE msg_id IN ({placeholders})", ids)
            cursor.execute("DELETE FROM chat_history WHERE timestamp BETWEEN ? AND ?", (start_iso, end_iso))
            cursor.execute("UPDATE summary_msg_counter SET count = MAX(0, count - ?), last_level1_at = MIN(last_level1_at, MAX(0, count - ?)), last_level2_at = MIN(last_level2_at, MAX(0, count - ?)), last_level3_at = MIN(last_level3_at, MAX(0, count - ?)) WHERE id = 1", (len(ids), len(ids), len(ids), len(ids)))
            return len(ids)
    return 0


def search_chat_messages(keyword: str, limit: int = 20):
    if not keyword or not keyword.strip():
        return []
    with get_conn() as conn:
        cursor = conn.cursor()
        # FTS5 MATCH 不支持标准参数化查询，必须手动转义双引号防止注入和语法错误
        safe_keyword = '"' + keyword.strip().replace('"', '""') + '"'
        cursor.execute('''
            SELECT f.rowid, f.content, h.role, h.timestamp,
                   snippet(chat_fts, 0, '<mark>', '</mark>', '...', 40) as snippet
            FROM chat_fts f
            JOIN chat_history h ON h.id = f.rowid
            WHERE chat_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        ''', (safe_keyword, limit))
        rows = cursor.fetchall()
    return [{"id": r["rowid"], "content": r["content"], "role": r["role"], "timestamp": r["timestamp"], "snippet": r["snippet"]} for r in rows]


def rebuild_fts_index():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_fts")
        cursor.execute("""
            INSERT INTO chat_fts(rowid, content)
            SELECT id, content FROM chat_history
        """)


def get_last_ai_message():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, content FROM chat_history WHERE role='assistant' ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
    return {"id": row["id"], "content": row["content"]} if row else None


def reroll_last_ai_message():
    """删除最后一条 AI 消息和对应的用户消息。返回删除前的用户消息。
    同时删除用户消息，避免 re-add 时出现重复。"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, content FROM chat_history WHERE role='user' ORDER BY id DESC LIMIT 1")
        user_row = cursor.fetchone()
        if not user_row:
            return None
        # 收集要删除的消息 id（用于重建索引）
        cursor.execute("SELECT id FROM chat_history WHERE id >= ?", (user_row["id"],))
        delete_ids = [r["id"] for r in cursor.fetchall()]
        deleted_count = len(delete_ids)
        cursor.execute("DELETE FROM chat_history WHERE id >= ?", (user_row["id"],))
        # 清理句向量索引
        if delete_ids:
            placeholders = ",".join("?" * len(delete_ids))
            cursor.execute(f"DELETE FROM sentence_index WHERE msg_id IN ({placeholders})", delete_ids)
        if deleted_count:
            cursor.execute("UPDATE summary_msg_counter SET count = MAX(0, count - ?) WHERE id = 1", (deleted_count,))
    return user_row["content"] if user_row else None


def reroll_from_message(msg_id):
    """从指定消息处重新生成，删除 msg_id 及之后的所有消息，返回之前最近的一条用户消息"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, content FROM chat_history WHERE role='user' AND id <= ? ORDER BY id DESC LIMIT 1", (msg_id,))
        user_row = cursor.fetchone()
        if not user_row:
            return None
        user_content = user_row["content"]
        user_msg_id = user_row["id"]
        cursor.execute("SELECT id FROM chat_history WHERE id >= ?", (user_msg_id,))
        delete_ids = [r["id"] for r in cursor.fetchall()]
        if delete_ids:
            placeholders = ','.join('?' for _ in delete_ids)
            cursor.execute(f"DELETE FROM chat_history WHERE id IN ({placeholders})", delete_ids)
            # 清理句向量索引
            cursor.execute(f"DELETE FROM sentence_index WHERE msg_id IN ({placeholders})", delete_ids)
            cursor.execute("UPDATE summary_msg_counter SET count = MAX(0, count - ?) WHERE id = 1", (len(delete_ids),))
    return user_content


def archive_message(msg_id):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE chat_history SET archived = 1 WHERE id = ?", (msg_id,))