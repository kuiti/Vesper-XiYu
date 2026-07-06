# core/shared_memory.py — 共同经历系统
"""共同经历系统：记录角色和用户之间的专属回忆、梗、笑点等共享时刻。"""
import json
import logging
from datetime import datetime
from core.db import get_conn

logger = logging.getLogger(__name__)


def ensure_table():
    """确保 shared_moments 表存在"""
    with get_conn() as conn:
        conn.cursor().execute("""CREATE TABLE IF NOT EXISTS shared_moments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER DEFAULT 0,
            text TEXT NOT NULL,
            moment_type TEXT DEFAULT 'general',
            importance REAL DEFAULT 0.5,
            created_at TEXT
        )""")
        conn.cursor().execute("CREATE INDEX IF NOT EXISTS idx_shared_moments_char ON shared_moments(character_id)")


def record_shared_moment(text: str, moment_type: str = "general", character_id: int = 0, importance: float = 0.5):
    """记录一条共同经历到数据库，需先确认 shared_memory 功能已启用。"""
    from core.character_card import CharacterCard
    if not CharacterCard.is_feature_enabled("shared_memory"):
        return
    ensure_table()
    now = datetime.now().isoformat()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO shared_moments (character_id, text, moment_type, importance, created_at) VALUES (?, ?, ?, ?, ?)",
            (character_id, text, moment_type, importance, now)
        )


def get_shared_moments(character_id: int = 0, limit: int = 20) -> list:
    """获取指定角色的共同经历列表，按时间倒序返回。"""
    ensure_table()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM shared_moments WHERE character_id=? ORDER BY created_at DESC LIMIT ?",
            (character_id, limit)
        )
        return [dict(r) for r in cursor.fetchall()]


def detect_moment(user_msg: str, ai_reply: str) -> str | None:
    """检测对话中是否产生了共同经历（如双方大笑、深度共鸣），返回类型或 None。"""
    from core.character_card import CharacterCard
    if not CharacterCard.is_feature_enabled("shared_memory"):
        return None
    laugh_words = ["哈哈", "笑死", "太好笑了", "哈哈哈", "lol", "😂"]
    deep_words = ["真的吗", "我也觉得", "你说得对", "确实是", "理解"]

    if any(w in user_msg for w in laugh_words) and any(w in ai_reply for w in laugh_words):
        return "laugh"
    if any(w in user_msg for w in deep_words) and len(ai_reply) > 100:
        return "deep"
    return None
