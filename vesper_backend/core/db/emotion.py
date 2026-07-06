# core/db/emotion.py  |  emotion_daily + emotion_log + empathy_feedback + ai_personality_traits + user_activity_stats
"""情绪与主动消息模块：情绪日志清理、用户活跃统计、主动推送管理。"""

import logging
from datetime import datetime, timedelta
from . import get_conn

logger = logging.getLogger(__name__)


# ========== 情绪日志清理 ==========

def cleanup_emotion_log(days: int = 90):
    """清理 N 天前的情绪日志，防止无限增长"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cursor.execute("DELETE FROM emotion_log WHERE timestamp < ?", (cutoff,))
        deleted = cursor.rowcount
    if deleted > 0:
        logger.info(f"[清理] 删除 {deleted} 条 {days} 天前的 emotion_log")
    return deleted


# ========== 用户活跃时段统计 ==========

def record_user_activity_hour():
    """记录当前小时的用户活跃"""
    hour = datetime.now().hour
    now = datetime.now().isoformat()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO user_activity_stats (hour, message_count, last_updated) VALUES (?, 1, ?) "
            "ON CONFLICT(hour) DO UPDATE SET message_count = message_count + 1, last_updated = ?",
            (hour, now, now)
        )


def get_active_hours(top_n: int = 3) -> list:
    """返回消息最多的前 N 个小时，如 [20, 21, 22]。"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT hour FROM user_activity_stats ORDER BY message_count DESC LIMIT ?",
            (top_n,)
        )
        return [r["hour"] for r in cursor.fetchall()]


# ========== 主动消息回复记录 ==========

def log_proactive_message(trigger_type: str, content: str):
    """记录一条主动推送的消息"""
    now = datetime.now().isoformat()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO proactive_response_log (timestamp, trigger_type, content, responded) VALUES (?, ?, ?, 0)",
            (now, trigger_type, content)
        )


def mark_proactive_responded():
    """用户回复后，标记最近一条主动消息为已回复"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE proactive_response_log SET responded = 1 "
            "WHERE id = (SELECT MAX(id) FROM proactive_response_log WHERE responded = 0)"
        )


def get_proactive_response_rate(days: int = 14) -> float:
    """计算最近 N 天主动消息回复率"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as total, SUM(responded) as responded "
            "FROM proactive_response_log "
            "WHERE timestamp >= datetime('now', ?)",
            (f"-{days} days",)
        )
        row = cursor.fetchone()
        total = row["total"] if row else 0
        if total == 0:
            return 0.25  # 无数据时默认偏低回复率，避免过度打扰用户
        return row["responded"] / total if total else 0.5


def get_proactive_cooldown_minutes() -> int:
    """根据回复率自动调整冷却时间（分钟）"""
    rate = get_proactive_response_rate(14)
    if rate >= 0.5:
        return 40
    elif rate >= 0.2:
        return 60
    else:
        return 120


# ========== 主动推送标志 ==========

def get_proactive_flag(key: str) -> str | None:
    """读取主动推送标志"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM proactive_flags WHERE key=?", (key,))
        row = cursor.fetchone()
    return row["value"] if row else None


def set_proactive_flag(key: str, value: str):
    """写入主动推送标志"""
    now = datetime.now().isoformat()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO proactive_flags (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, now)
        )