# core/emotion_evolution.py — AI 情绪自主演化引擎
"""
长期维度上 AI 情绪的自主演化：沉默衰减、冷淡适应、温暖回升、习惯亲近、周日反思。
与 relationship.py 配合——relationship 负责"单次互动调整"，本模块负责"时间跨度演化"。
"""

from datetime import datetime, timedelta
from core.db import get_conn, get_config, set_config
import logging
from core.retry import silent_exc
logger = logging.getLogger(__name__)


# 性格特征上下限
TRAIT_MIN = 0.0
TRAIT_MAX = 1.0

# 特征默认值 (OCEAN 五维)
TRAIT_DEFAULTS = {
    "openness": 0.4,           # O 开放性
    "conscientiousness": 0.3,  # C 尽责性
    "extraversion": 0.5,       # E 外向性
    "agreeableness": 0.5,      # A 宜人性
    "neuroticism": 0.3,        # N 神经质
}

# 特征文字描述映射
TRAIT_DESCRIPTIONS = {
    "extraversion": {
        "high": "外向活泼，喜欢社交互动，精力充沛",
        "mid": "性格适中，该活跃时活跃，该安静时安静",
        "low": "内向安静，喜欢独处，回复简洁克制"
    },
    "agreeableness": {
        "high": "温和友善，善解人意，乐于配合",
        "mid": "态度适中，有原则但不固执",
        "low": "直率坦白，不太在意他人感受"
    },
    "conscientiousness": {
        "high": "认真负责，做事有条理，会主动跟进",
        "mid": "适度认真，不会过分纠结细节",
        "low": "随性散漫，不太在意计划和细节"
    },
    "openness": {
        "high": "富有想象力，喜欢尝试新事物，思维开放",
        "mid": "适度开放，愿意接受新想法",
        "low": "保守传统，喜欢熟悉的事物"
    },
    "neuroticism": {
        "high": "情绪波动大，容易受用户情绪影响",
        "mid": "情绪相对稳定，偶尔有起伏",
        "low": "情绪稳定，不容易被外界影响"
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
    from core.relationship import MIN_VALUE, MAX_VALUE, invalidate_relationship_cache
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
            cursor.execute("INSERT INTO relationship (key, value, updated_at) VALUES (?, ?, ?)", (key, max(MIN_VALUE, min(MAX_VALUE, initial + delta)), now))
    invalidate_relationship_cache()


def _get_last_evolution_date() -> str | None:
    """从 DB 读取上次演化日期"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key='last_evolution_date'")
        row = cursor.fetchone()
    return row["value"] if row else None


def _set_last_evolution_date(date_str: str):
    """持久化上次演化日期（原子化：只有当天未执行过才写入成功）"""
    set_config("last_evolution_date", date_str)


def _try_claim_evolution_date(today: str) -> bool:
    """检查当日是否已演化的缓存安全版本。"""
    current = get_config("last_evolution_date", "")
    if current == today:
        return False
    set_config("last_evolution_date", today)
    return True


# ─── 每日演化主入口 ───


def process_daily_evolution():
    """每日触发一次。检查所有时间维度演化规则。"""
    today = datetime.now().strftime("%Y-%m-%d")
    # 原子抢占：防止并发重复执行
    if not _try_claim_evolution_date(today):
        return

    print(f"[情绪演化] 开始每日演化检查 ({today})")

    # 获取距上次互动的小时数
    hours_since = _get_hours_since_last_interaction()

    # ─── 检测持续低落（用于主动触发 C）───
    _check_sustained_low_mood()

    # ─── 规则1: 沉默衰减（使用独立键名，防止被 _try_claim_evolution_date 覆写）───
    _rule_silence_decay(hours_since)

    # ─── 规则2: 冷淡适应 ───
    _rule_cold_adaptation()

    # ─── 规则3: 习惯亲近 ───
    _rule_habitual_closeness()

    # ─── 规则4: 互动质量驱动的 trait 微调 ───
    _rule_interaction_quality()

    # ─── 规则5: 每日互动 → expressiveness 微增（让用户感知系统在运行）───
    try:
        from core.emotion_tracker import get_emotion_trend
        today_trend = get_emotion_trend(1)
        if today_trend and today_trend[0]["total_messages"] > 0:
            update_trait("agreeableness", 0.01)
            print(f"[情绪演化] 今日互动 → expressiveness+0.01")
    except Exception as e:
        silent_exc("?", e)

    # ─── 规则6: 周日反思 ───
    if datetime.now().weekday() == 6:
        _rule_weekly_reflection()

    # 规则执行完毕后再写日期
    _set_last_evolution_date(today)
    # 清理 90 天前的旧日志，防止无限膨胀
    try:
        from core.db import get_conn
        with get_conn() as conn:
            conn.cursor().execute("DELETE FROM emotion_log WHERE timestamp < date('now', '-90 days')")
    except Exception as e:
        silent_exc("?", e)
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
            set_proactive_flag("low_mood_consecutive_days", "")
            print(f"[情绪演化] 情绪已恢复，清除持续低落标记")


def _get_last_decay_date() -> str | None:
    """获取上次沉默衰减的日期（独立于演化日期，防止被 _try_claim_evolution_date 覆写）"""
    return get_config("last_decay_date", None)


def _rule_silence_decay(hours_since: float | None):
    """沉默衰减：连续 3+ 天无互动 → affection -0.2/天，trust -0.1/天（最多10天递减）
    增量计算：仅衰减自上次演化以来的天数，避免重启重复衰减。"""
    if hours_since is None:
        return
    days = hours_since / 24
    if days < 3:
        return

    # 增量衰减：使用独立的 decay 日期（而非 last_evolution_date，因后者已被 _try_claim_evolution_date 覆写为今天）
    last_decay = _get_last_decay_date()
    if last_decay:
        last = datetime.fromisoformat(last_decay)
        days_since_last = (datetime.now() - last).days
    else:
        days_since_last = 1  # 首次运行只衰减1天，后续每日增量
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

    # 记录本次衰减日期
    set_config("last_decay_date", datetime.now().strftime("%Y-%m-%d"))

    # 沉默也影响 initiative（AI 不太想主动打扰）
    if days > 7:
        update_trait("conscientiousness", -0.05)

    print(f"[情绪演化] 沉默衰减: {int(days)}天(增量{effective_days}天) → affection{affection_loss:+.1f} trust{trust_loss:+.1f}")


def _rule_cold_adaptation():
    """冷淡适应：用户情绪偏负面占比高 → optimism -0.05，expressiveness -0.03"""
    from core.emotion_tracker import get_emotion_trend
    trend = get_emotion_trend(7)
    if len(trend) < 2:
        return

    negative_days = sum(1 for d in trend if d["score"] < -5)
    total_days = len(trend)
    neg_ratio = negative_days / total_days if total_days > 0 else 0
    if neg_ratio > 0.5:
        update_trait("extraversion", -0.05)
        update_trait("agreeableness", -0.03)
        _log_evolution_event(
            "autonomous_adaptation",
            f"用户{negative_days}天情绪负面（占比{neg_ratio:.0%}），AI进入自我保护状态，乐观度-0.05",
            0, 0
        )
        print(f"[情绪演化] 冷淡适应: 负面占比{neg_ratio:.0%} → optimism-0.05")


def _rule_habitual_closeness():
    """习惯亲近：近期频繁互动 → 信任缓慢积累"""
    from core.emotion_tracker import get_emotion_trend
    trend = get_emotion_trend(7)
    if len(trend) < 3:
        return

    active_days = sum(1 for d in trend if d["total_messages"] > 0)
    if active_days >= 3:
        _update_relationship_value("trust", 0.05)
        _log_evolution_event(
            "habitual_closeness",
            f"近{len(trend)}天有{active_days}天互动，习惯成自然，信任+0.05",
            0, 0.05
        )
        print(f"[情绪演化] 习惯亲近: {active_days}/{len(trend)}天有互动 → trust+0.05")


def _rule_interaction_quality():
    """互动质量驱动的 trait 微调：基于最近交互模式"""
    from core.emotion_tracker import get_emotion_trend
    trend = get_emotion_trend(14)
    if len(trend) < 2:
        return

    positive_days = sum(1 for d in trend if d["score"] > 5)
    total_days = len(trend)
    positive_ratio = positive_days / total_days if total_days > 0 else 0

    # 正面互动多 → 提升 openness 和 extraversion，降低 neuroticism
    if positive_ratio > 0.5:
        update_trait("openness", 0.03)
        update_trait("extraversion", 0.02)
        update_trait("neuroticism", -0.01)
        print(f"[情绪演化] 正面互动占比{positive_ratio:.0%} → openness+0.03 extraversion+0.02 neuroticism-0.01")

    # 负面互动多 → 提升 neuroticism
    negative_days = sum(1 for d in trend if d["score"] < -3)
    negative_ratio = negative_days / total_days if total_days > 0 else 0
    if negative_ratio > 0.4:
        update_trait("neuroticism", 0.02)
        print(f"[情绪演化] 负面互动占比{negative_ratio:.0%} → neuroticism+0.02")

    # 用户发消息多 → 提升 agreeableness
    avg_msgs = sum(d["total_messages"] for d in trend) / total_days
    if avg_msgs > 5:
        update_trait("agreeableness", 0.02)
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
        update_trait("extraversion", 0.05)
        adjust_log.append("optimism+0.05")
        if has_deep_chat:
            update_trait("agreeableness", 0.03)
            adjust_log.append("expressiveness+0.03")

    # 本周负面为主
    if negative_days >= 4:
        update_trait("extraversion", -0.05)
        adjust_log.append("optimism-0.05")

    # 用户活跃 → AI 更主动
    total_msgs = sum(d["total_messages"] for d in trend)
    if total_msgs > 100:
        update_trait("conscientiousness", 0.03)
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
    if traits["extraversion"] >= 0.6:
        parts.append("比较乐观")
    elif traits["extraversion"] <= 0.3:
        parts.append("偏向悲观")

    if traits["agreeableness"] >= 0.6:
        parts.append("善于表达")
    elif traits["agreeableness"] <= 0.3:
        parts.append("话少寡言")

    if traits["conscientiousness"] >= 0.6:
        parts.append("会主动关心你")
    elif traits["conscientiousness"] <= 0.2:
        parts.append("不太主动")

    if traits["openness"] >= 0.6:
        parts.append("爱开玩笑")
    elif traits["openness"] <= 0.2:
        parts.append("比较严肃")

    summary = f"{ai_name}当前是一个{'、'.join(parts) if parts else '性格平衡'}的AI伙伴。"

    return {
        "traits": {k: round(v, 2) for k, v in traits.items()},
        "descriptions": descriptions,
        "summary": summary
    }


def get_emotion_timeline(days: int = 30) -> dict:
    """返回前端图表所需的时间线数据（包含好感/信任历史曲线）"""
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

        # 好感/信任历史：取每天最后一条 emotion_log 的 affection_after 和 trust_after
        cursor.execute(
            "SELECT date(timestamp) as day, MAX(timestamp) as max_ts FROM emotion_log WHERE timestamp >= ? GROUP BY date(timestamp) ORDER BY day",
            (start,)
        )
        day_ts_map = {r["day"]: r["max_ts"] for r in cursor.fetchall()}
        affection_history = []
        trust_history = []
        for day, ts in sorted(day_ts_map.items()):
            cursor.execute(
                "SELECT affection_after, trust_after FROM emotion_log WHERE timestamp = ?",
                (ts,)
            )
            row = cursor.fetchone()
            if row:
                affection_history.append({"date": day, "value": round(row["affection_after"], 1)})
                trust_history.append({"date": day, "value": round(row["trust_after"], 1)})

    # 当天数据永远用当前实际值（覆盖旧日志中可能过时的记录）
    from core.relationship import get_relationship
    cur_aff, cur_trust = get_relationship()
    today = datetime.now().strftime("%Y-%m-%d")
    # 移除旧的今天记录（如果有的话），用当前值替换
    affection_history = [h for h in affection_history if h["date"] != today]
    trust_history = [h for h in trust_history if h["date"] != today]
    affection_history.append({"date": today, "value": round(cur_aff, 1)})
    trust_history.append({"date": today, "value": round(cur_trust, 1)})

    return {
        "daily_emotion": daily_emotion,
        "events": events,
        "affection_history": affection_history,
        "trust_history": trust_history
    }
