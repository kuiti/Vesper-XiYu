# core/db/misc.py  |  achievements + ai_diary + schedule + favorites + conversation_summary + documents

from datetime import datetime
from . import get_conn


# ========== 收藏消息 ==========

def get_favorites():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM favorites ORDER BY created_at DESC")
        return [dict(r) for r in cursor.fetchall()]


def add_favorite(msg_id, content, role, timestamp):
    with get_conn() as conn:
        conn.cursor().execute("INSERT OR IGNORE INTO favorites (msg_id, content, role, timestamp) VALUES (?, ?, ?, ?)", (msg_id, content, role, timestamp))


def remove_favorite(msg_id):
    with get_conn() as conn:
        conn.cursor().execute("DELETE FROM favorites WHERE msg_id = ?", (msg_id,))


def is_favorite(msg_id):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM favorites WHERE msg_id = ?", (msg_id,))
        return cursor.fetchone() is not None


# ========== 文档管理 ==========

def add_document(filename, chunks, size):
    with get_conn() as conn:
        cursor = conn.cursor()
        uploaded_at = datetime.now().isoformat()
        cursor.execute("INSERT INTO documents (filename, chunks, size, uploaded_at) VALUES (?, ?, ?, ?)", (filename, chunks, size, uploaded_at))
        doc_id = cursor.lastrowid
    return doc_id


def get_documents():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents ORDER BY id DESC")
        rows = cursor.fetchall()
    return [{"id": r["id"], "filename": r["filename"], "chunks": r["chunks"], "size": r["size"], "uploaded_at": r["uploaded_at"]} for r in rows]


def get_knowledge_filenames():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT filename FROM documents")
        return [r["filename"] for r in cursor.fetchall()]


def delete_document(doc_id):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))


# ========== 成就系统 ==========

ACHIEVEMENTS = [
    ("first_chat", "初次对话", "发送第一条消息"),
    ("ten_messages", "话匣子", "累计发送10条消息"),
    ("hundred_messages", "老友", "累计发送100条消息"),
    ("thousand_messages", "知己", "累计发送1000条消息"),
    ("seven_days", "一周", "连续7天有对话"),
    ("thirty_days", "月度", "累计30天有对话"),
    ("late_night", "夜猫子", "在凌晨0-5点发消息"),
    ("affection_50", "有好感", "好感度首次突破50"),
    ("affection_80", "深深", "好感度首次突破80"),
    ("trust_50", "信任", "信任度首次突破50"),
    ("trust_80", "完全信任", "信任度首次突破80"),
]


def check_achievements(msg_count, consecutive_days, total_days, hour, affection, trust):
    if hour is None:
        hour = -1
    unlocked = []
    with get_conn() as conn:
        cursor = conn.cursor()
        # 一次性查询获取所有已解锁 key，避免 N+1
        cursor.execute("SELECT key FROM achievements")
        unlocked_keys = {r["key"] for r in cursor.fetchall()}
        for key, name, desc in ACHIEVEMENTS:
            if key in unlocked_keys:
                continue
            unlock = False
            if key == "first_chat" and msg_count >= 1: unlock = True
            elif key == "ten_messages" and msg_count >= 10: unlock = True
            elif key == "hundred_messages" and msg_count >= 100: unlock = True
            elif key == "thousand_messages" and msg_count >= 1000: unlock = True
            elif key == "seven_days" and consecutive_days >= 7: unlock = True
            elif key == "thirty_days" and total_days >= 30: unlock = True
            elif key == "late_night" and hour in (0,1,2,3,4,5): unlock = True
            elif key == "affection_50" and affection >= 50: unlock = True
            elif key == "affection_80" and affection >= 80: unlock = True
            elif key == "trust_50" and trust >= 50: unlock = True
            elif key == "trust_80" and trust >= 80: unlock = True
            if unlock:
                now = datetime.now().isoformat()
                cursor.execute("INSERT OR IGNORE INTO achievements (key, name, description, unlocked_at) VALUES (?, ?, ?, ?)", (key, name, desc, now))
                unlocked.append({"key": key, "name": name, "description": desc})
    return unlocked


def get_achievements():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM achievements ORDER BY unlocked_at DESC")
        return [dict(r) for r in cursor.fetchall()]


def get_all_achievement_defs():
    return [{"key": k, "name": n, "description": d} for k, n, d in ACHIEVEMENTS]


# ========== AI日记 ==========

def save_diary_entry(date, content, mood):
    with get_conn() as conn:
        conn.cursor().execute("INSERT OR REPLACE INTO ai_diary (date, content, mood) VALUES (?, ?, ?)", (date, content, mood))


def get_diary_entries(limit=30):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ai_diary ORDER BY date DESC LIMIT ?", (limit,))
        return [dict(r) for r in cursor.fetchall()]