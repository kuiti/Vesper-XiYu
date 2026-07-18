# core/db/misc.py  |  achievements + ai_diary + schedule + favorites + conversation_summary + documents
"""杂项功能模块：成就系统、AI日记、收藏消息、文档管理。"""

from datetime import datetime
from . import get_conn, get_chat_conn


# ========== 收藏消息 ==========

def get_favorites(character_id: int = 0):
    """获取所有收藏消息，按时间倒序排列。"""
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM favorites ORDER BY created_at DESC")
        return [dict(r) for r in cursor.fetchall()]


def add_favorite(msg_id, content, role, timestamp, character_id: int = 0):
    """收藏一条消息（重复收藏自动忽略）。"""
    with get_chat_conn(character_id) as conn:
        conn.cursor().execute("INSERT OR IGNORE INTO favorites (msg_id, content, role, timestamp) VALUES (?, ?, ?, ?)", (msg_id, content, role, timestamp))


def remove_favorite(msg_id, character_id: int = 0):
    """取消收藏指定消息。"""
    with get_chat_conn(character_id) as conn:
        conn.cursor().execute("DELETE FROM favorites WHERE msg_id = ?", (msg_id,))


def is_favorite(msg_id, character_id: int = 0):
    """判断消息是否已收藏。"""
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM favorites WHERE msg_id = ?", (msg_id,))
        return cursor.fetchone() is not None


# ========== 文档管理 ==========

def add_document(filename, chunks, size, character_id: int = 0):
    """添加文档记录（per-character），返回文档 ID。"""
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        uploaded_at = datetime.now().isoformat()
        cursor.execute("INSERT INTO documents (filename, chunks, size, character_id, uploaded_at) VALUES (?, ?, ?, ?, ?)",
                       (filename, chunks, size, character_id, uploaded_at))
        doc_id = cursor.lastrowid
    return doc_id


def get_documents(character_id: int = 0):
    """获取指定角色的文档记录。"""
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE character_id = ? ORDER BY id DESC", (character_id,))
        rows = cursor.fetchall()
    return [{"id": r["id"], "filename": r["filename"], "chunks": r["chunks"], "size": r["size"], "uploaded_at": r["uploaded_at"]} for r in rows]


def get_knowledge_filenames():
    """获取所有已上传文档的文件名列表（遍历各角色库）。"""
    filenames = []
    seen = set()
    # 查角色 0 的默认库
    try:
        with get_chat_conn(0) as conn:
            for r in conn.cursor().execute("SELECT filename FROM documents").fetchall():
                if r["filename"] not in seen:
                    seen.add(r["filename"])
                    filenames.append(r["filename"])
    except Exception:
        pass
    return filenames


def delete_document(doc_id, character_id: int = 0):
    """删除指定角色的文档记录。"""
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))


# ========== AI日记 ==========

def save_diary_entry(date, content, mood, character_id: int = 0):
    """保存 AI 日记（同日期覆盖）。"""
    with get_chat_conn(character_id) as conn:
        conn.cursor().execute("INSERT OR REPLACE INTO ai_diary (date, content, mood) VALUES (?, ?, ?)", (date, content, mood))


def get_diary_entries(limit=30, character_id: int = 0):
    """获取最近 N 条 AI 日记。"""
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ai_diary ORDER BY date DESC LIMIT ?", (limit,))
        return [dict(r) for r in cursor.fetchall()]