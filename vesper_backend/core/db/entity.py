# core/db/entity.py  |  entities + knowledge_graph + sentence_index + memory_importance
"""实体与知识图谱模块：记忆重要性追踪、知识三元组存储与查询。
per-character: entities/knowledge_graph 在角色库。
memory_importance 暂时还在主库，未迁移。
"""

from datetime import datetime
from . import get_chat_conn


# ========== memory_importance ==========

def get_memory_importance(memory_id, character_id: int = 0):
    """获取记忆重要性"""
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT importance, last_accessed, access_count, ignored_count FROM memory_importance WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        if row:
            return {"importance": row["importance"], "last_accessed": row["last_accessed"], "access_count": row["access_count"], "ignored_count": row["ignored_count"] or 0}
        return {"importance": 5.0, "last_accessed": None, "access_count": 0, "ignored_count": 0}


def set_memory_importance(memory_id, importance, created_at=None, character_id: int = 0):
    """设置记忆重要性"""
    if created_at is None:
        created_at = datetime.now().isoformat()
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO memory_importance (id, importance, last_accessed, access_count, created_at)
                          VALUES (?, ?, ?, 0, ?)
                          ON CONFLICT(id) DO UPDATE SET importance = ?, last_accessed = ?""",
                       (memory_id, importance, None, created_at, importance, None))


def update_memory_access(memory_id, character_id: int = 0):
    """更新记忆访问时间和次数"""
    now = datetime.now().isoformat()
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO memory_importance (id, importance, last_accessed, access_count, created_at)
                          VALUES (?, 5.0, ?, 1, ?)
                          ON CONFLICT(id) DO UPDATE SET
                          last_accessed = ?,
                          access_count = access_count + 1""",
                       (memory_id, now, now, now))


def get_all_memory_importance(character_id: int = 0):
    """获取所有记忆重要性"""
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, importance, last_accessed, access_count, ignored_count, created_at FROM memory_importance")
        return {row["id"]: {"importance": row["importance"], "last_accessed": row["last_accessed"],
                           "access_count": row["access_count"], "ignored_count": row["ignored_count"],
                           "created_at": row["created_at"]}
                for row in cursor.fetchall()}


def increment_ignored_batch(ids: list, character_id: int = 0):
    """批量递增未被 MMR 选中的候选的忽略计数"""
    if not ids:
        return
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.executemany(
            """INSERT INTO memory_importance (id, ignored_count)
               VALUES (?, 1)
               ON CONFLICT(id) DO UPDATE SET
               ignored_count = COALESCE(ignored_count, 0) + 1""",
            [(sid,) for sid in ids]
        )


# ========== knowledge_graph ==========

def add_knowledge_triplet(subject, predicate, obj, confidence=0.7, source_msg_id=None, character_id=0):
    """添加知识图谱三元组（per-character）"""
    now = datetime.now().isoformat()
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, confidence FROM knowledge_graph WHERE subject = ? AND predicate = ? AND object = ?",
                       (subject, predicate, obj))
        existing = cursor.fetchone()
        if existing:
            new_conf = max(existing["confidence"], confidence)
            cursor.execute("UPDATE knowledge_graph SET confidence = ?, updated_at = ? WHERE id = ?",
                          (new_conf, now, existing["id"]))
        else:
            cursor.execute("INSERT INTO knowledge_graph (subject, predicate, object, confidence, source_msg_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (subject, predicate, obj, confidence, source_msg_id, now, now))


def query_knowledge_by_entity(entity, character_id=0):
    """查询与实体相关的所有三元组（per-character）"""
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT subject, predicate, object, confidence FROM knowledge_graph WHERE subject = ? OR object = ? ORDER BY confidence DESC LIMIT 20",
                       (entity, entity))
        return [{"subject": r["subject"], "predicate": r["predicate"], "object": r["object"], "confidence": r["confidence"]}
                for r in cursor.fetchall()]


def get_all_knowledge(character_id=0):
    """获取所有知识图谱三元组（per-character）"""
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT subject, predicate, object, confidence FROM knowledge_graph ORDER BY confidence DESC LIMIT 100")
        return [{"subject": r["subject"], "predicate": r["predicate"], "object": r["object"], "confidence": r["confidence"]}
                for r in cursor.fetchall()]