# core/db/cleanup.py  |  clear_chat_history + 批量清理函数

import sqlite3
from datetime import datetime, timedelta
from . import get_conn


def clear_chat_history():
    """清空所有聊天记录、摘要、关联数据，并重建 FTS"""
    from .summary import reset_msg_counter, reset_active_memory
    with get_conn() as conn:
        cursor = conn.cursor()
        # 临时禁用 FTS 触发器，避免 FTS 表损坏导致删除失败
        cursor.execute("DROP TRIGGER IF EXISTS chat_ad")
        cursor.execute("DROP TRIGGER IF EXISTS chat_ai")
        cursor.execute("DROP TRIGGER IF EXISTS chat_au")
        cursor.execute("DELETE FROM chat_history")
        cursor.execute("DELETE FROM tiered_summary")
        cursor.execute("DELETE FROM death_archive")
        # 清理本轮新增的关联数据
        cursor.execute("DELETE FROM entities")
        cursor.execute("DELETE FROM memory_history")
        cursor.execute("DELETE FROM knowledge_graph")
        cursor.execute("DELETE FROM sentence_index")
        cursor.execute("DELETE FROM memory_importance")
        cursor.execute("DELETE FROM favorites")
        cursor.execute("DELETE FROM empathy_feedback")
        cursor.execute("DELETE FROM user_profile WHERE key LIKE '_fact_%'")
        # 重建 FTS 表并恢复触发器
        cursor.execute("INSERT INTO chat_fts(chat_fts) VALUES('rebuild')")
        cursor.execute("""CREATE TRIGGER IF NOT EXISTS chat_ai AFTER INSERT ON chat_history BEGIN
            INSERT INTO chat_fts(rowid, content) VALUES (new.id, new.content);
        END""")
        cursor.execute("""CREATE TRIGGER IF NOT EXISTS chat_ad AFTER DELETE ON chat_history BEGIN
            INSERT INTO chat_fts(chat_fts, rowid, content) VALUES('delete', old.id, old.content);
        END""")
        cursor.execute("""CREATE TRIGGER IF NOT EXISTS chat_au AFTER UPDATE ON chat_history BEGIN
            INSERT INTO chat_fts(chat_fts, rowid, content) VALUES('delete', old.id, old.content);
            INSERT INTO chat_fts(rowid, content) VALUES (new.id, new.content);
        END""")
    reset_msg_counter()
    reset_active_memory()