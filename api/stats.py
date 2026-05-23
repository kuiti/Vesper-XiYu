from fastapi import APIRouter
from core.db import get_conn, get_config
from datetime import datetime, timedelta

router = APIRouter(prefix="/stats", tags=["stats"])

@router.get("/overview")
async def get_overview():
    now = datetime.now()
    with get_conn() as conn:
        cursor = conn.cursor()
        # 消息总数
        cursor.execute("SELECT COUNT(*) as cnt FROM chat_history")
        total = cursor.fetchone()["cnt"]
        # 用户消息数
        cursor.execute("SELECT COUNT(*) as cnt FROM chat_history WHERE role='user'")
        user_msgs = cursor.fetchone()["cnt"]
        # AI消息数
        ai_msgs = total - user_msgs
        # 互动天数
        cursor.execute("SELECT COUNT(DISTINCT substr(timestamp,1,10)) as days FROM chat_history")
        total_days = cursor.fetchone()["days"] or 0
        # 日均消息
        avg_daily = round(total / total_days, 1) if total_days > 0 else 0
        # 活跃时段分布 (按小时)
        cursor.execute("SELECT substr(timestamp,12,2) as hour, COUNT(*) as cnt FROM chat_history GROUP BY hour ORDER BY hour")
        hourly = {r["hour"]: r["cnt"] for r in cursor.fetchall()}
        # 最活跃时段
        peak_hour = max(hourly, key=hourly.get) if hourly else None
        # 情绪分布
        cursor.execute("SELECT sum(positive_count) as pos, sum(negative_count) as neg, sum(neutral_count) as neu FROM emotion_daily")
        row = cursor.fetchone()
        pos, neg, neu = (row["pos"] or 0), (row["neg"] or 0), (row["neu"] or 0)
        # 最近30天消息趋势
        thirty_ago = (now - timedelta(days=30)).isoformat()[:10]
        cursor.execute("SELECT substr(timestamp,1,10) as date, COUNT(*) as cnt FROM chat_history WHERE timestamp >= ? GROUP BY date ORDER BY date", (thirty_ago,))
        daily_trend = [{"date": r["date"], "count": r["cnt"]} for r in cursor.fetchall()]
        # 关键词云 (消息中最常见的词)
        cursor.execute("SELECT content FROM chat_history WHERE role='user' ORDER BY id DESC LIMIT 500")
        words = {}
        import re
        for r in cursor.fetchall():
            for w in re.findall(r'[一-鿿]{2,4}', r["content"]):
                words[w] = words.get(w, 0) + 1
        top_words = sorted(words.items(), key=lambda x: -x[1])[:20]

    ai_name = get_config("ai_name", "佐仓")
    return {
        "total_messages": total,
        "user_messages": user_msgs,
        "ai_messages": ai_msgs,
        "total_days": total_days,
        "avg_daily": avg_daily,
        "peak_hour": peak_hour,
        "hourly_dist": {str(k): v for k, v in sorted(hourly.items())},
        "emotion_dist": {"positive": pos, "negative": neg, "neutral": neu},
        "daily_trend": daily_trend[-30:],
        "top_words": [{"word": w, "count": c} for w, c in top_words],
        "ai_name": ai_name
    }
