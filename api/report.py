from fastapi import APIRouter, Query
from core.db import get_conn, get_config
from datetime import datetime, timedelta

router = APIRouter(prefix="/report", tags=["report"])

@router.get("/monthly")
async def monthly_report(month: str = Query(default="")):
    if not month:
        month = datetime.now().strftime("%Y-%m")
    start = month + "-01"
    ai_name = get_config("ai_name", "佐仓")
    user_name = get_config("user_name", "我")

    with get_conn() as conn:
        cursor = conn.cursor()
        # 消息统计
        cursor.execute("SELECT COUNT(*) as cnt FROM chat_history WHERE timestamp >= ? AND timestamp < date(?, '+1 month')", (start, start))
        total = cursor.fetchone()["cnt"]
        cursor.execute("SELECT COUNT(DISTINCT substr(timestamp,1,10)) as days FROM chat_history WHERE timestamp >= ? AND timestamp < date(?, '+1 month')", (start, start))
        active_days = cursor.fetchone()["days"] or 0
        # 情绪
        cursor.execute("SELECT sum(positive_count) as pos, sum(negative_count) as neg, sum(neutral_count) as neu FROM emotion_daily WHERE date >= ? AND date < date(?, '+1 month')", (start, start))
        row = cursor.fetchone()
        pos, neg, neu = (row["pos"] or 0), (row["neg"] or 0), (row["neu"] or 0)
        # 最活跃日
        cursor.execute("SELECT substr(timestamp,1,10) as d, COUNT(*) as cnt FROM chat_history WHERE timestamp >= ? AND timestamp < date(?, '+1 month') GROUP BY d ORDER BY cnt DESC LIMIT 1", (start, start))
        peak = cursor.fetchone()
        peak_day = f"{peak['d']} ({peak['cnt']}条)" if peak else "无"
        # 成就
        cursor.execute("SELECT name FROM achievements WHERE unlocked_at >= ? AND unlocked_at < date(?, '+1 month')", (start, start))
        achievements = [r["name"] for r in cursor.fetchall()]
        # 关系变化
        cursor.execute("SELECT affection_after, trust_after FROM emotion_log WHERE timestamp >= ? AND timestamp < date(?, '+1 month') ORDER BY timestamp DESC LIMIT 1", (start, start))
        rel = cursor.fetchone()

    total_emotion = pos + neg + neu
    mood = "以正面情绪为主，心情不错！" if pos > neg else "以负面情绪为主，需要更多关怀。" if neg > pos else "情绪平稳。"
    if total_emotion == 0: mood = "暂无情绪数据。"

    lines = [
        f"# {ai_name} · {month} 月度报告\n",
        f"## 📊 聊天统计",
        f"- {user_name}和{ai_name}共发了 **{total}** 条消息",
        f"- 活跃天数：**{active_days}** 天",
        f"- 最活跃的一天：{peak_day}",
        f"",
        f"## 😊 情绪概况",
        f"- {mood}",
        f"- 正面：{pos} | 负面：{neg} | 中性：{neu}",
        f"",
    ]
    if achievements:
        lines.append(f"## 🏆 本月解锁成就\n- " + "\n- ".join(achievements) + "\n")
    if rel:
        lines.append(f"## 💕 关系状态\n- 好感度：{rel['affection_after']} | 信任度：{rel['trust_after']}\n")

    lines.append(f"\n> 报告由 {ai_name} 自动生成 · {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    return {"ok": True, "content": "\n".join(lines), "month": month, "stats": {"total": total, "active_days": active_days, "pos": pos, "neg": neg, "neu": neu, "achievements": achievements}}
