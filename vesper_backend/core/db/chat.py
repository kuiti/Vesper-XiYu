# core/db/chat.py  |  chat_history CRUD（路由到角色独立库）
"""聊天记录 CRUD 模块：会话管理、消息增删改查、全文搜索。"""

import logging
from datetime import datetime, timedelta
import core.db as _db_mod

logger = logging.getLogger(__name__)


def _get_chat(character_id=0):
    """延迟查找 get_chat_conn，支持 monkeypatch"""
    return _db_mod.get_chat_conn(character_id)


# ========== chat_sessions ==========

def _ensure_session_column(character_id=0):
    """确保 chat_history 表有 session_id 列（迁移旧数据）"""
    conn = _get_chat(character_id)
    cursor = conn.cursor()
    # 检查 session_id 列是否存在
    cursor.execute("PRAGMA table_info(chat_history)")
    cols = {r["name"] for r in cursor.fetchall()}
    if "session_id" not in cols:
        cursor.execute("ALTER TABLE chat_history ADD COLUMN session_id INTEGER DEFAULT 1")
        conn.commit()
    # 确保至少有一个 session
    cursor.execute("SELECT COUNT(*) as cnt FROM chat_sessions")
    if cursor.fetchone()["cnt"] == 0:
        now = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO chat_sessions (name, created_at, updated_at, is_active) VALUES (?, ?, ?, 1)",
            ("默认对话", now, now)
        )
        conn.commit()


def get_active_session_id(character_id=0) -> int:
    """获取当前活跃 session ID"""
    _ensure_session_column(character_id)
    conn = _get_chat(character_id)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM chat_sessions WHERE is_active = 1 LIMIT 1")
    row = cursor.fetchone()
    if row:
        return row["id"]
    # 没有活跃 session，创建默认
    now = datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO chat_sessions (name, created_at, updated_at, is_active) VALUES (?, ?, ?, 1)",
        ("默认对话", now, now)
    )
    conn.commit()
    return cursor.lastrowid


def list_sessions(character_id=0) -> list:
    """列出所有会话"""
    _ensure_session_column(character_id)
    conn = _get_chat(character_id)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, created_at, updated_at, message_count, is_active FROM chat_sessions ORDER BY updated_at DESC")
    return [dict(r) for r in cursor.fetchall()]


def create_session(name: str = "新对话", character_id=0) -> int:
    """创建新会话，取消其他活跃，返回新 session ID"""
    _ensure_session_column(character_id)
    conn = _get_chat(character_id)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("UPDATE chat_sessions SET is_active = 0")
    cursor.execute(
        "INSERT INTO chat_sessions (name, created_at, updated_at, is_active) VALUES (?, ?, ?, 1)",
        (name, now, now)
    )
    conn.commit()
    return cursor.lastrowid


def switch_session(session_id: int, character_id=0):
    """切换到指定会话"""
    _ensure_session_column(character_id)
    conn = _get_chat(character_id)
    cursor = conn.cursor()
    cursor.execute("UPDATE chat_sessions SET is_active = 0")
    cursor.execute("UPDATE chat_sessions SET is_active = 1, updated_at = ? WHERE id = ?",
                   (datetime.now().isoformat(), session_id))
    conn.commit()


def delete_session(session_id: int, character_id=0):
    """删除会话及其消息"""
    _ensure_session_column(character_id)
    conn = _get_chat(character_id)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
    cursor.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
    conn.commit()


def rename_session(session_id: int, name: str, character_id=0):
    """重命名会话"""
    _ensure_session_column(character_id)
    conn = _get_chat(character_id)
    cursor = conn.cursor()
    cursor.execute("UPDATE chat_sessions SET name = ? WHERE id = ?", (name, session_id))
    conn.commit()


# ========== chat_history ==========
def get_all_chat_messages(character_id: int = 0, session_id: int = 0, limit: int = 0):
    """获取全部聊天消息，支持按角色和会话过滤。"""
    conn = _get_chat(character_id)
    cursor = conn.cursor()
    if session_id:
        if limit:
            cursor.execute("SELECT role, content, timestamp FROM chat_history WHERE session_id = ? ORDER BY id LIMIT ?", (session_id, limit))
        else:
            cursor.execute("SELECT role, content, timestamp FROM chat_history WHERE session_id = ? ORDER BY id", (session_id,))
    else:
        if limit:
            cursor.execute("SELECT role, content, timestamp FROM chat_history ORDER BY id LIMIT ?", (limit,))
        else:
            cursor.execute("SELECT role, content, timestamp FROM chat_history ORDER BY id")
    rows = cursor.fetchall()
    return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]


def get_recent_chat_messages(limit: int = 100, character_id: int = 0, session_id: int = 0):
    """获取最近 N 条消息（倒序查询后反转，保证时间正序）"""
    conn = _get_chat(character_id)
    cursor = conn.cursor()
    if session_id:
        cursor.execute("SELECT role, content, timestamp FROM chat_history WHERE session_id = ? ORDER BY id DESC LIMIT ?", (session_id, limit))
    else:
        cursor.execute("SELECT role, content, timestamp FROM chat_history ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in reversed(rows)]


def get_last_user_messages(n=3, character_id=0, session_id=0):
    """获取最近 n 条用户消息（按时间倒序）"""
    conn = _get_chat(character_id)
    cursor = conn.cursor()
    if session_id:
        cursor.execute(
            "SELECT role, content, timestamp FROM chat_history WHERE role='user' AND session_id=? ORDER BY id DESC LIMIT ?",
            (session_id, n)
        )
    else:
        cursor.execute(
            "SELECT role, content, timestamp FROM chat_history WHERE role='user' ORDER BY id DESC LIMIT ?",
            (n,)
        )
    rows = cursor.fetchall()
    return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]


def add_chat_message(role, content, timestamp=None, character_id=0, session_id=0):
    """添加一条聊天消息，自动更新会话计数。"""
    if timestamp is None:
        timestamp = datetime.now().isoformat()
    if not session_id:
        session_id = get_active_session_id(character_id)
    conn = _get_chat(character_id)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_history (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                   (session_id, role, content, timestamp))
    # 更新 session 的 message_count 和 updated_at
    cursor.execute("UPDATE chat_sessions SET message_count = message_count + 1, updated_at = ? WHERE id = ?",
                   (timestamp, session_id))
    conn.commit()
    return cursor.lastrowid


def update_chat_message(msg_id: int, content: str, character_id=0):
    """更新指定聊天消息的内容。"""
    conn = _get_chat(character_id)
    conn.cursor().execute("UPDATE chat_history SET content = ? WHERE id = ?", (content, msg_id))
    conn.commit()


def delete_chat_history_between(start_iso: str, end_iso: str, character_id=0):
    """删除时间段内的聊天记录。同步清理关联表（favorites/sentence_index/empathy_feedback）。"""
    conn = _get_chat(character_id)
    cursor = conn.cursor()
    # 先拿待删 id 列表（用于清理共享库关联表）
    cursor.execute(
        "SELECT id FROM chat_history WHERE timestamp >= ? AND timestamp <= ?",
        (start_iso, end_iso),
    )
    ids = [r[0] for r in cursor.fetchall()]
    if not ids:
        return 0
    cursor.execute(
        "DELETE FROM chat_history WHERE timestamp >= ? AND timestamp <= ?",
        (start_iso, end_iso),
    )
    deleted = cursor.rowcount
    conn.commit()
    # 共享库的关联表需要手动级联清理（角色库无 FTS5，但 favorites/sentence_index/empathy_feedback 在共享库）
    _cascade_cleanup_msg_refs(ids, character_id=character_id)
    return deleted


def delete_chat_history_older_than(days: int, character_id=0):
    """删除指定天数之前的聊天记录。同步清理关联表。"""
    conn = _get_chat(character_id)
    cursor = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cursor.execute("SELECT id FROM chat_history WHERE timestamp < ?", (cutoff,))
    ids = [r[0] for r in cursor.fetchall()]
    if not ids:
        return 0
    cursor.execute("DELETE FROM chat_history WHERE timestamp < ?", (cutoff,))
    deleted = cursor.rowcount
    conn.commit()
    _cascade_cleanup_msg_refs(ids, character_id=character_id)
    return deleted


def _cascade_cleanup_msg_refs(ids: list[int], character_id=0):
    """清理引用了已删消息 id 的关联表。

    favorites / empathy_feedback 在主库。
    sentence_index 在主库但有 character_id 列，需按角色过滤删除。
    """
    if not ids:
        return
    try:
        import core.db as _db_mod
        main_conn = _db_mod.get_conn()
        mc = main_conn.cursor()
        # 分批 IN 子句，避免 SQLITE_MAX_VARIABLE_NUMBER（默认 999）超限
        for i in range(0, len(ids), 500):
            batch = ids[i:i + 500]
            placeholders = ",".join("?" * len(batch))
            for tbl in ("favorites",):
                try:
                    mc.execute(f"DELETE FROM {tbl} WHERE msg_id IN ({placeholders})", batch)
                except Exception as e:
                    logger.warning(f"[chat] 级联清理 {tbl} 失败: {e}")
            # empathy_feedback 在 chat 库
            try:
                chat_conn = _db_mod.get_chat_conn(character_id)
                cc = chat_conn.cursor()
                cc.execute(f"DELETE FROM empathy_feedback WHERE msg_id IN ({placeholders})", batch)
                chat_conn.commit()
            except Exception as e:
                logger.warning(f"[chat] 级联清理 empathy_feedback 失败: {e}")
            # sentence_index 有 character_id 列，需按角色过滤
            try:
                mc.execute(
                    f"DELETE FROM sentence_index WHERE character_id = ? AND msg_id IN ({placeholders})",
                    (character_id, *batch)
                )
            except Exception as e:
                logger.warning(f"[chat] 级联清理 sentence_index 失败: {e}")
        main_conn.commit()
    except Exception as e:
        logger.warning(f"[chat] 级联清理失败: {e}")


def search_chat_messages(keyword: str, limit: int = 20, character_id=0):
    """搜索角色库聊天记录（FTS5 优先，降级到 LIKE）。"""
    if not keyword or not keyword.strip():
        return []
    keyword_stripped = keyword.strip()

    conn = _get_chat(character_id)
    cursor = conn.cursor()
    # FTS5 搜索（角色库也有 chat_fts）
    safe_keyword = '"' + keyword_stripped.replace('"', '""') + '"'
    try:
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
    except Exception as e:
        logger.warning(f"[chat] FTS5 搜索失败，降级到 LIKE: {e}")
        try:
            cursor.execute(
                "SELECT id as rowid, content, role, timestamp, substr(content, 1, 40) as snippet "
                "FROM chat_history WHERE content LIKE ? ORDER BY id DESC LIMIT ?",
                (f"%{keyword_stripped}%", limit)
            )
            rows = cursor.fetchall()
        except Exception:
            return []
    return [{"id": r["rowid"], "content": r["content"], "role": r["role"], "timestamp": r["timestamp"], "snippet": r["snippet"]} for r in rows]


def rebuild_fts_index():
    """重建 FTS5 全文搜索索引。"""
    with _db_mod.get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_fts")
        cursor.execute("INSERT INTO chat_fts(rowid, content) SELECT id, content FROM chat_history")


def get_last_ai_message(character_id=0):
    """获取最后一条 AI 消息。"""
    conn = _get_chat(character_id)
    cursor = conn.cursor()
    cursor.execute("SELECT id, content FROM chat_history WHERE role='assistant' ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    return {"id": row["id"], "content": row["content"]} if row else None


def reroll_last_ai_message(character_id=0):
    """删除最后一条 AI 消息和对应的用户消息。返回删除前的用户消息。"""
    conn = _get_chat(character_id)
    cursor = conn.cursor()
    cursor.execute("SELECT id, content FROM chat_history WHERE role='user' ORDER BY id DESC LIMIT 1")
    user_row = cursor.fetchone()
    if not user_row:
        return None
    cursor.execute("DELETE FROM chat_history WHERE id >= ?", (user_row["id"],))
    conn.commit()
    return user_row["content"] if user_row else None


def reroll_from_message(msg_id, character_id=0):
    """从指定消息处重新生成"""
    conn = _get_chat(character_id)
    cursor = conn.cursor()
    cursor.execute("SELECT id, content FROM chat_history WHERE role='user' AND id <= ? ORDER BY id DESC LIMIT 1", (msg_id,))
    user_row = cursor.fetchone()
    if not user_row:
        return None
    user_content = user_row["content"]
    user_msg_id = user_row["id"]
    cursor.execute("DELETE FROM chat_history WHERE id >= ?", (user_msg_id,))
    conn.commit()
    return user_content


def archive_message(msg_id, character_id=0):
    """将指定消息标记为已归档。"""
    conn = _get_chat(character_id)
    cursor = conn.cursor()
    cursor.execute("UPDATE chat_history SET archived = 1 WHERE id = ?", (msg_id,))
    conn.commit()
