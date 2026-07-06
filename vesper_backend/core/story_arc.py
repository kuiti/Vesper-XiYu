# core/story_arc.py — 故事线追踪
"""跟踪跨对话的故事弧"""
from core.db import get_conn
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def ensure_arc_table():
    """确保 story_arcs 表存在，不存在则自动创建"""
    with get_conn() as conn:
        conn.cursor().execute("""CREATE TABLE IF NOT EXISTS story_arcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            status TEXT DEFAULT 'active',
            progress TEXT DEFAULT '{}',
            created_at TEXT,
            updated_at TEXT
        )""")


def create_arc(name: str) -> int:
    """创建新故事线，返回故事线 ID"""
    ensure_arc_table()
    now = datetime.now().isoformat()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO story_arcs (name, created_at, updated_at) VALUES (?, ?, ?)",
            (name, now, now)
        )
        return cursor.lastrowid


def get_active_arcs() -> list:
    """获取活跃的故事线"""
    ensure_arc_table()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM story_arcs WHERE status='active' ORDER BY updated_at DESC")
        return [dict(r) for r in cursor.fetchall()]


def update_arc_progress(arc_id: int, progress: dict):
    """更新故事线进度"""
    ensure_arc_table()
    now = datetime.now().isoformat()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE story_arcs SET progress=?, updated_at=? WHERE id=?",
            (json.dumps(progress, ensure_ascii=False), now, arc_id)
        )


def close_arc(arc_id: int):
    """关闭故事线"""
    ensure_arc_table()
    now = datetime.now().isoformat()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE story_arcs SET status='closed', updated_at=? WHERE id=?", (now, arc_id))
