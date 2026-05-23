# core/emotion_evolution.py — AI 情绪自主演化引擎
"""
长期维度上 AI 情绪的自主演化：沉默衰减、冷淡适应、温暖回升、习惯亲近、周日反思。
与 relationship.py 配合——relationship 负责"单次互动调整"，本模块负责"时间跨度演化"。
"""

from datetime import datetime, timedelta
from core.db import get_conn, get_config, set_config


# 性格特征上下限
TRAIT_MIN = 0.0
TRAIT_MAX = 1.0

# 特征默认值
TRAIT_DEFAULTS = {
    "optimism": 0.5,
    "expressiveness": 0.5,
    "initiative": 0.3,
    "playfulness": 0.4
}

# 特征文字描述映射
TRAIT_DESCRIPTIONS = {
    "optimism": {
        "high": "乐观开朗，对未来充满期待",
        "mid": "心态平衡，不太悲观也不太乐观",
        "low": "偏向悲观，对事物持谨慎态度"
    },
    "expressiveness": {
        "high": "善于表达，会主动分享自己的感受和想法",
        "mid": "表达适中，该说话时说话",
        "low": "话少寡言，回复简洁克制"
    },
    "initiative": {
        "high": "主动关心用户，经常发起话题",
        "mid": "适度主动，不会过分打扰",
        "low": "被动回应，不太主动发起互动"
    },
    "playfulness": {
        "high": "爱开玩笑，经常调侃用户",
        "mid": "偶尔幽默，看场合开玩笑",
        "low": "严肃认真，很少开玩笑"
    }
}


def _now():
    return datetime.now().isoformat()


_traits_initialized = False


def init_traits():
    """首次运行时初始化特征表（仅第一次调用时执行 INSERT）"""
    global _traits_initialized
    if _traits_initialized:
        return
    _traits_initialized = True
    now = _now()
    with get_conn() as conn:
        cursor = conn.cursor()
        for key, default_val in TRAIT_DEFAULTS.items():
            cursor.execute(
                "INSERT OR IGNORE INTO ai_personality_traits (key, value, updated_at) VALUES (?, ?, ?)",
                (key, default_val, now)
            )


def get_trait(key: str) -> float:
    """获取单个特征值"""
    init_traits()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM ai_personality_traits WHERE key=?", (key,))
        row = cursor.fetchone()
    return row["value"] if row else TRAIT_DEFAULTS.get(key, 0.5)


def get_all_traits() -> dict:
    """获取全部四个特征值"""
    init_traits()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM ai_personality_traits")
        rows = cursor.fetchall()
    result = dict(TRAIT_DEFAULTS)
    for r in rows:
        result[r["key"]] = r["value"]
    return result


def update_trait(key: str, delta: float):
    """更新单个特征值（带上下限保护）"""
    current = get_trait(key)
    new_val = max(TRAIT_MIN, min(TRAIT_MAX, current + delta))
    if abs(new_val - current) < 0.01:
        return
    now = _now()
    with get_conn() as conn:
        conn.cursor().execute(
            "UPDATE ai_personality_traits SET value=?, updated_at=? WHERE key=?",
            (new_val, now, key)
        )


def _log_evolution_event(event_type: str, reason: str, affection_delta: float = 0, trust_delta: float = 0):
    """记录一次自主演化事件到 emotion_log"""
    from core.relationship import get_relationship, get_ai_emotion
    affection, trust = get_relationship()
    ai_emotion = get_ai_emotion()
    now = _now()
    with get_conn() as conn:
        conn.cursor().execute(
            "INSERT INTO emotion_log (timestamp, event_type, affection_delta, trust_delta, affection_after, trust_after, ai_emotion_after, reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (now, event_type, affection_delta, trust_delta, affection, trust, ai_emotion, reason)
        )


def _update_relationship_value(key: str, delta: float):
    """安全更新关系值（复用 relationship 的模式）"""
    from core.relationship import MIN_VALUE, MAX_VALUE
    now = _now()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM relationship WHERE key=?", (key,))
        row = cursor.fetchone()
        if row:
            new_val = max(MIN_VALUE, min(MAX_VALUE, row["value"] + delta))
            cursor.execute("UPDATE relationship SET value=?, updated_at=? WHERE key=?", (new_val, now, key))
        else:
            from core.relationship import INITIAL_AFFECTION, INITIAL_TRUST
            initial = INITIAL_AFFECTION if key == "affection" else INITIAL_TRUST
            cursor.execute("INSERT INTO relationship (key, value, updated_at) VALUES (?, ?, ?)", (key, initial + delta, now))


def _get_last_evolution_date() -> str | None:
    """从 DB 读取上次演化日期"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key='last_evolution_date'")
        row = cursor.fetchone()
    return row["value"] if row else None


def _set_last_evolution_date(date_str: str):
    """持久化上次演化日期"""
    set_config("last_evolution_date", date_str)


# ─── 每日演化主入口 ───


def process_daily_evolution():
    """每日触发一次。检查所有时间维度演化规则。"""
    today = datetime.now().strftime("%Y-%m-%d")
    last = _get_last_evolution_date()
    if last == today:
        return

    print(f"[情绪演化] 开始每日演化检查 ({today})")

    # 获取距上次互动的小时数
    hours_since = _get_hours_since_last_interaction()

    # ─── 检测持续低落（用于主动触发 C）───
    _check_sustained_low_mood()

    # ─── 规则1: 沉默衰减 ───
    _rule_silence_decay(hours_since)

    # ─── 规则2: 冷淡适应 ───
    _rule_cold_adaptation()

    # ─── 规则3: 习惯亲近 ───
    _rule_habitual_closeness()

    # ─── 规则4: 互动质量驱动的 trait 微调 ───
    _rule_interaction_quality()

    # ─── 规则5: 周日反思 ───
    if datetime.now().weekday() == 6:
        _rule_weekly_reflection()

    # 规则执行完毕后再写日期
    _set_last_evolution_date(today)
    print(f"[情绪演化] 每日演化完成")


# ─── 演化规则 ───

def _get_hours_since_last_interaction() -> float | None:
    """获取距上次互动的小时数"""
    try:
        last_str = get_config("last_chat_time", "")
        if last_str:
            last = datetime.fromisoformat(last_str)
            return (datetime.now() - last).total_seconds() / 3600
    except Exception as e:
        print(f"[情绪演化] 读取上次互动时间失败: {e}")
        pass
    return None


def _check_sustained_low_mood():
    """检测用户情绪是否持续低落 >= 3 天。若是，写 proactive_flag 供主动触发 C 读取。"""
    from core.emotion_tracker import get_emotion_trend
    from core.db import set_proactive_flag, get_proactive_flag
    trend = get_emotion_trend(7)
    if len(trend) < 3:
        return

    # 统计连续最近的负分天数
    consecutive_negative = 0
    for d in reversed(trend):
        if d["score"] < -3:
            consecutive_negative += 1
        else:
            break

    if consecutive_negative >= 3:
        # 情绪持续低落，只在未标记时写标记
        existing = get_proactive_flag("sustained_low_mood")
        if not existing or existing != datetime.now().strftime("%Y-%m-%d"):
            set_proactive_flag("sustained_low_mood", datetime.now().strftime("%Y-%m-%d"))
            set_proactive_flag("low_mood_consecutive_days", str(consecutive_negative))
            print(f"[情绪演化] 检测到持续低落 {consecutive_negative} 天，写入主动触发标记")
    else:
        # 情绪恢复，清除标记
        existing = get_proactive_flag("sustained_low_mood")
        if existing:
            set_proactive_flag("sustained_low_mood", "")
            print(f"[情绪演化] 情绪已恢复，清除持续低落标记")


def _rule_silence_decay(hours_since: float | None):
    """沉默衰减：连续 3+ 天无互动 → affection -0.2/天，trust -0.1/天（最多10天递减）
    增量计算：仅衰减自上次演化以来的天数，避免重启重复衰减。"""
    if hours_since is None:
        return
    days = hours_since / 24
    if days < 3:
        return

    # 增量衰减：计算自上次衰减以来的天数
    last_decay = _get_last_evolution_date()
    if last_decay:
        last = datetime.fromisoformat(last_decay)
        days_since_last = (datetime.now() - last).days
    else:
        days_since_last = min(int(days), 10)
    effective_days = min(days_since_last, 10)

    if effective_days <= 0:
        return

    affection_loss = -0.2 * effective_days
    trust_loss = -0.1 * effective_days

    _update_relationship_value("affection", affection_loss)
    _update_relationship_value("trust", trust_loss)
    _log_evolution_event(
        "time_decay",
        f"用户沉默{int(days)}天，好感-{abs(affection_loss):.1f}，信任-{abs(trust_loss):.1f}",
        affection_loss, trust_loss
    )

    # 沉默也影响 initiative（AI 不太想主动打扰）
    if days > 7:
        update_trait("initiative", -0.05)

    print(f"[情绪演化] 沉默衰减: {int(days)}天(增量{effective_days}天) → affection{affection_loss:+.1f} trust{trust_loss:+.1f}")


def _rule_cold_adaptation():
    """冷淡适应：连续 7 天用户情绪偏负面 → optimism -0.1，expressiveness -0.05"""
    from core.emotion_tracker import get_emotion_trend
    trend = get_emotion_trend(7)
    if len(trend) < 5:
        return

    negative_days = sum(1 for d in trend if d["score"] < -5)
    if negative_days < 7 and len(trend) < 7:
        return

    # 计算负面占比
    neg_ratio = negative_days / len(trend)
    if neg_ratio > 0.7:
        update_trait("optimism", -0.1)
        update_trait("expressiveness", -0.05)
        _log_evolution_event(
            "autonomous_adaptation",
            f"用户连续{negative_days}天情绪负面（占比{neg_ratio:.0%}），AI进入自我保护状态，乐观度-0.1",
            0, 0
        )
        print(f"[情绪演化] 冷淡适应: 负面占比{neg_ratio:.0%} → optimism-0.1")


def _rule_habitual_closeness():
    """习惯亲近：连续 30 天每天有互动 → trust +0.05/天（缓慢积累）"""
    from core.emotion_tracker import get_emotion_trend
    trend = get_emotion_trend(30)
    if len(trend) < 21:  # 至少21天数据才判断
        return

    active_days = sum(1 for d in trend if d["total_messages"] > 0)
    if active_days >= 28:  # 28天以上有互动
        _update_relationship_value("trust", 0.05)
        _log_evolution_event(
            "habitual_closeness",
            f"连续{active_days}天有互动，习惯成自然，信任+0.05",
            0, 0.05
        )
        print(f"[情绪演化] 习惯亲近: {active_days}/30天有互动 → trust+0.05")


def _rule_interaction_quality():
    """互动质量驱动的 trait 微调：基于最近30天的互动模式"""
    from core.emotion_tracker import get_emotion_trend
    trend = get_emotion_trend(30)
    if len(trend) < 10:
        return

    positive_days = sum(1 for d in trend if d["score"] > 5)
    total_days = len(trend)
    positive_ratio = positive_days / total_days

    # 正面互动多 → 提升 playfulness 和 optimism
    if positive_ratio > 0.6:
        update_trait("playfulness", 0.03)
        update_trait("optimism", 0.02)
        print(f"[情绪演化] 正面互动占比{positive_ratio:.0%} → playfulness+0.03 optimism+0.02")

    # 用户发消息多 → 提升 expressiveness
    avg_msgs = sum(d["total_messages"] for d in trend) / total_days
    if avg_msgs > 20:
        update_trait("expressiveness", 0.02)
        print(f"[情绪演化] 日均{avg_msgs:.0f}条消息 → expressiveness+0.02")


def _rule_weekly_reflection():
    """周日反思：综合本周互动质量，微调所有 traits"""
    from core.emotion_tracker import get_emotion_trend
    trend = get_emotion_trend(7)

    positive_days = sum(1 for d in trend if d["score"] > 5)
    negative_days = sum(1 for d in trend if d["score"] < -5)
    has_deep_chat = any(d["total_messages"] > 30 for d in trend)

    traits = get_all_traits()
    adjust_log = []

    # 本周正面为主
    if positive_days >= 4:
        update_trait("optimism", 0.05)
        adjust_log.append("optimism+0.05")
        if has_deep_chat:
            update_trait("expressiveness", 0.03)
            adjust_log.append("expressiveness+0.03")

    # 本周负面为主
    if negative_days >= 4:
        update_trait("optimism", -0.05)
        adjust_log.append("optimism-0.05")

    # 用户活跃 → AI 更主动
    total_msgs = sum(d["total_messages"] for d in trend)
    if total_msgs > 100:
        update_trait("initiative", 0.03)
        adjust_log.append("initiative+0.03")

    if adjust_log:
        summary = f"周日反思：本周{'正面为主' if positive_days >= 4 else '负面为主' if negative_days >= 4 else '平稳'}，" + "，".join(adjust_log)
        _log_evolution_event("weekly_reflection", summary, 0, 0)
        print(f"[情绪演化] 周日反思: {summary}")


# ─── 前端数据接口 ───

def get_trait_profile() -> dict:
    """获取 AI 性格画像（含文字描述）"""
    traits = get_all_traits()
    descriptions = {}
    for key, val in traits.items():
        desc_map = TRAIT_DESCRIPTIONS.get(key, {})
        if val >= 0.7:
            desc = desc_map.get("high", "")
        elif val >= 0.4:
            desc = desc_map.get("mid", "")
        else:
            desc = desc_map.get("low", "")
        descriptions[key] = desc

    # 生成综合文字描述
    ai_name = get_config("ai_name", "佐仓")
    parts = []
    if traits["optimism"] >= 0.6:
        parts.append("比较乐观")
    elif traits["optimism"] <= 0.3:
        parts.append("偏向悲观")

    if traits["expressiveness"] >= 0.6:
        parts.append("善于表达")
    elif traits["expressiveness"] <= 0.3:
        parts.append("话少寡言")

    if traits["initiative"] >= 0.6:
        parts.append("会主动关心你")
    elif traits["initiative"] <= 0.2:
        parts.append("不太主动")

    if traits["playfulness"] >= 0.6:
        parts.append("爱开玩笑")
    elif traits["playfulness"] <= 0.2:
        parts.append("比较严肃")

    summary = f"{ai_name}当前是一个{'、'.join(parts) if parts else '性格平衡'}的AI伙伴。"

    return {
        "traits": {k: round(v, 2) for k, v in traits.items()},
        "descriptions": descriptions,
        "summary": summary
    }


def get_emotion_timeline(days: int = 30) -> dict:
    """返回前端图表所需的时间线数据"""
    from core.emotion_tracker import get_emotion_trend

    daily_emotion = get_emotion_trend(days)
    start = (datetime.now() - timedelta(days=days)).isoformat()

    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT timestamp, event_type, reason, affection_delta, trust_delta, ai_emotion_after FROM emotion_log WHERE timestamp >= ? ORDER BY timestamp ASC LIMIT 100",
            (start,)
        )
        events = [dict(r) for r in cursor.fetchall()]

    return {
        "daily_emotion": daily_emotion,
        "events": events
    }
