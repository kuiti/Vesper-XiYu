import asyncio
from fastapi import APIRouter
from core.db import get_conn, get_config
from datetime import datetime, timedelta

router = APIRouter(prefix="/stats", tags=["stats"])

def _get_overview_sync():
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
        # 关键词云 (jieba 分词)
        cursor.execute("SELECT content FROM chat_history WHERE role='user' ORDER BY id DESC LIMIT 500")
        words = {}
        try:
            import jieba
            _stopwords = {"可以", "已经", "不是", "我们", "他们", "她们", "什么", "怎么", "这个", "那个", "因为", "所以", "如果", "但是", "可以", "就是", "没有", "知道", "现在", "自己", "出来", "起来", "时候", "觉得", "可能", "应该", "这样", "那样", "这些", "那些", "还是", "或者", "而且", "不过", "然后", "已经", "正在", "一直", "一个", "一些", "这个", "那个"}
            for r in cursor.fetchall():
                for w in jieba.cut(r["content"]):
                    w = w.strip()
                    if len(w) >= 2 and w not in _stopwords:
                        words[w] = words.get(w, 0) + 1
        except ImportError:
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


@router.get("/overview")
async def get_overview():
    return await asyncio.to_thread(_get_overview_sync)
