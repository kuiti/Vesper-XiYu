# core/db/cleanup.py  |  clear_chat_history + 批量清理函数（per-character）
"""数据清理模块：清空指定角色的聊天记录及关联数据，重建全文索引。"""

from . import get_conn, get_chat_conn


def clear_chat_history(character_id: int = 0):
    """清空指定角色的聊天记录、摘要、关联数据，并重建 FTS"""
    from .summary import reset_msg_counter, reset_active_memory
    with get_chat_conn(character_id) as conn:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()
        cursor.execute("DROP TRIGGER IF EXISTS chat_ad")
        cursor.execute("DROP TRIGGER IF EXISTS chat_ai")
        cursor.execute("DROP TRIGGER IF EXISTS chat_au")
        cursor.execute("DELETE FROM chat_history")
        cursor.execute("DELETE FROM tiered_summary")
        cursor.execute("DELETE FROM death_archive")
        cursor.execute("DELETE FROM entities")
        cursor.execute("DELETE FROM memory_history")
        cursor.execute("DELETE FROM knowledge_graph")
        cursor.execute("DELETE FROM user_profile WHERE key LIKE '_fact_%'")
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
        conn.commit()
    # 主库的全局表（sentence_index / memory_importance / favorites / empathy_feedback）
    if not character_id:
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sentence_index")
            cursor.execute("DELETE FROM memory_importance")
            cursor.execute("DELETE FROM favorites")
            cursor.execute("DELETE FROM empathy_feedback")
    else:
        # per-character：sentence_index 有 character_id 列，按角色删除
        with get_conn() as conn:
            conn.cursor().execute("DELETE FROM sentence_index WHERE character_id = ?", (character_id,))
    reset_msg_counter(character_id=character_id)
    reset_active_memory()