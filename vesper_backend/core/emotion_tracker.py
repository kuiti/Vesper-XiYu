# core/emotion_tracker.py — 情绪追踪模块（按角色隔离）
"""每日情绪分数累计，用于曲线和趋势分析"""

from datetime import datetime, timedelta


def record_emotion(emotion: str, character_id: int = 0):
    """每条消息的情绪分析后调用
    positive → score += 2
    negative → score -= 2
    neutral  → score += 0.1（正常交流本身偏正面）
    """
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().isoformat()

    if emotion == "positive":
        delta, field = 2.0, "positive_count"
    elif emotion == "negative":
        delta, field = -2.0, "negative_count"
    else:
        delta, field = 0.1, "neutral_count"

    from core.db import get_chat_conn
    conn = get_chat_conn(character_id)
    cursor = conn.cursor()
    pos = 1 if emotion == "positive" else 0
    neg = 1 if emotion == "negative" else 0
    neu = 1 if emotion == "neutral" else 0
    allowed_fields = {"positive_count", "negative_count", "neutral_count"}
    if field not in allowed_fields:
        field = "neutral_count"
    cursor.execute(
        f"INSERT INTO emotion_daily (date, score, positive_count, negative_count, neutral_count, total_messages, updated_at) "
        f"VALUES (?, ?, ?, ?, ?, 1, ?) "
        f"ON CONFLICT(date) DO UPDATE SET score=score+?, {field}={field}+1, total_messages=total_messages+1, updated_at=?",
        (today, delta, pos, neg, neu, now, delta, now)
    )
    conn.commit()


def get_emotion_trend(days: int = 7, character_id: int = 0) -> list:
    """获取最近 N 天的情绪趋势"""
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    from core.db import get_chat_conn
    conn = get_chat_conn(character_id)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT date, score, positive_count, negative_count, neutral_count, total_messages FROM emotion_daily WHERE date >= ? ORDER BY date",
        (start,)
    )
    rows = cursor.fetchall()
    return [{
        "date": r["date"],
        "score": round(r["score"], 1),
        "positive_count": r["positive_count"],
        "negative_count": r["negative_count"],
        "neutral_count": r["neutral_count"],
        "total_messages": r["total_messages"]
    } for r in rows]


def get_today_emotion(character_id: int = 0) -> dict:
    """获取今日情绪状态"""
    today = datetime.now().strftime("%Y-%m-%d")
    from core.db import get_chat_conn
    conn = get_chat_conn(character_id)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT date, score, positive_count, negative_count, neutral_count, total_messages FROM emotion_daily WHERE date=?",
        (today,)
    )
    row = cursor.fetchone()
    if not row:
        return {"date": today, "score": 0, "positive_count": 0, "negative_count": 0, "neutral_count": 0, "total_messages": 0}
    return {
        "date": row["date"],
        "score": round(row["score"], 1),
        "positive_count": row["positive_count"],
        "negative_count": row["negative_count"],
        "neutral_count": row["neutral_count"],
        "total_messages": row["total_messages"]
    }


def get_emotion_summary(character_id: int = 0) -> str:
    """生成情绪摘要文本，用于注入 prompt 或主动关怀"""
    trend = get_emotion_trend(7, character_id)
    if not trend:
        return ""

    today = get_today_emotion(character_id)
    total_score = sum(d["score"] for d in trend)
    avg_score = total_score / len(trend)

    # 连续负面天数
    consecutive_negative = 0
    for d in reversed(trend):
        if d["score"] < -3:
            consecutive_negative += 1
        else:
            break

    parts = []
    if avg_score > 5:
        parts.append("最近一周情绪整体偏正面")
    elif avg_score < -5:
        parts.append("最近一周情绪整体偏负面")
    else:
        parts.append("最近一周情绪比较平稳")

    if today["total_messages"] > 0:
        if today["score"] > 3:
            parts.append("今天心情不错")
        elif today["score"] < -3:
            parts.append("今天情绪偏低")

    if consecutive_negative >= 3:
        parts.append(f"已连续{consecutive_negative}天情绪偏负面，需要关注")

    return "；".join(parts) if parts else ""
