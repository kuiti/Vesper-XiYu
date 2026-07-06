# core/emotion_evolution.py — AI 情绪自主演化引擎（per-character）
"""
长期维度上 AI 情绪的自主演化：沉默衰减、冷淡适应、温暖回升、习惯亲近、周日反思。
与 relationship.py 配合——relationship 负责"单次互动调整"，本模块负责"时间跨度演化"。

per-character 设计：
- OCEAN 五维、relationship、emotion_log、mention_weights、correction_memory、feedback_memory
  全部存在角色库 get_chat_conn(character_id)
- 不同角色有独立的性格演化路径，互不污染
- 全局状态（last_evolution_date / last_chat_time / last_decay_date）仍在主库 config，
  因为是调度状态，不区分角色
"""

from datetime import datetime, timedelta
from core.db import get_conn, get_chat_conn, get_config, set_config
import logging
import threading
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
    """获取当前时间的 ISO 格式字符串"""
    return datetime.now().isoformat()


# per-character 初始化标记：{character_id: bool}
_traits_initialized: dict = {}
_traits_init_lock = threading.Lock()
_evolution_claim_lock = threading.Lock()


def init_traits(character_id: int = 0):
    """首次运行时初始化该角色的特征表（仅第一次调用时执行 INSERT）"""
    if _traits_initialized.get(character_id):
        return
    with _traits_init_lock:
        if _traits_initialized.get(character_id):
            return
        _traits_initialized[character_id] = True
    now = _now()
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        for key, default_val in TRAIT_DEFAULTS.items():
            cursor.execute(
                "INSERT OR IGNORE INTO ai_personality_traits (key, value, updated_at) VALUES (?, ?, ?)",
                (key, default_val, now)
            )


def get_trait(key: str, character_id: int = 0) -> float:
    """获取单个特征值（per-character）"""
    init_traits(character_id)
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT value FROM ai_personality_traits WHERE key=?",
            (key,),
        )
        row = cursor.fetchone()
    return row["value"] if row else TRAIT_DEFAULTS.get(key, 0.5)


def get_all_traits(character_id: int = 0) -> dict:
    """获取指定角色的全部特征值"""
    init_traits(character_id)
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT key, value FROM ai_personality_traits",
            (),
        )
        rows = cursor.fetchall()
    result = dict(TRAIT_DEFAULTS)
    for r in rows:
        result[r["key"]] = r["value"]
    return result


def update_trait(key: str, delta: float, character_id: int = 0):
    """更新单个特征值（带上下限保护，per-character）"""
    current = get_trait(key, character_id)
    new_val = max(TRAIT_MIN, min(TRAIT_MAX, current + delta))
    if abs(new_val - current) < 0.01:
        return
    now = _now()
    with get_chat_conn(character_id) as conn:
        conn.cursor().execute(
            "UPDATE ai_personality_traits SET value=?, updated_at=? WHERE key=?",
            (new_val, now, key)
        )


def _log_evolution_event(event_type: str, reason: str,
                          affection_delta: float = 0, trust_delta: float = 0,
                          character_id: int = 0):
    """记录一次自主演化事件到该角色的 emotion_log"""
    from core.relationship import get_relationship, get_ai_emotion
    affection, trust = get_relationship(character_id)
    ai_emotion = get_ai_emotion(character_id)
    now = _now()
    with get_chat_conn(character_id) as conn:
        conn.cursor().execute(
            "INSERT INTO emotion_log (timestamp, event_type, affection_delta, trust_delta, affection_after, trust_after, ai_emotion_after, reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (now, event_type, affection_delta, trust_delta, affection, trust, ai_emotion, reason)
        )


def _update_relationship_value(key: str, delta: float, character_id: int = 0):
    """安全更新关系值（per-character，复用 relationship 的模式）"""
    from core.relationship import MIN_VALUE, MAX_VALUE, invalidate_relationship_cache
    now = _now()
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM relationship WHERE key=?", (key,))
        row = cursor.fetchone()
        if row:
            new_val = max(MIN_VALUE, min(MAX_VALUE, row["value"] + delta))
            cursor.execute("UPDATE relationship SET value=?, updated_at=? WHERE key=?", (new_val, now, key))
        else:
            from core.relationship import INITIAL_AFFECTION, INITIAL_TRUST
            initial = INITIAL_AFFECTION if key == "affection" else INITIAL_TRUST
            cursor.execute("INSERT INTO relationship (key, value, updated_at) VALUES (?, ?, ?)",
                          (key, max(MIN_VALUE, min(MAX_VALUE, initial + delta)), now))
    invalidate_relationship_cache(character_id)


# ─── 全局调度状态（在主库 config，不区分角色）───

def _get_last_evolution_date() -> str | None:
    """从主库 config 读取上次演化日期（全局调度状态）"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key='last_evolution_date'")
        row = cursor.fetchone()
    return row["value"] if row else None


def _set_last_evolution_date(date_str: str):
    """持久化上次演化日期到主库 config"""
    set_config("last_evolution_date", date_str)


def _try_claim_evolution_date(today: str) -> bool:
    """检查当日是否已演化的缓存安全版本（全局锁，不区分角色）"""
    with _evolution_claim_lock:
        key = "last_evolution_date"
        current = get_config(key, "")
        if current == today:
            return False
        set_config(key, today)
        return True


def _get_hours_since_last_interaction() -> float | None:
    """获取距上次互动的小时数（全局，不区分角色）"""
    try:
        last_str = get_config("last_chat_time", "")
        if last_str:
            last = datetime.fromisoformat(last_str)
            return (datetime.now() - last).total_seconds() / 3600
    except Exception as e:
        logger.warning(f"[情绪演化] 读取上次互动时间失败: {e}")
        pass
    return None


def _get_last_decay_date() -> str | None:
    """获取上次沉默衰减的日期（全局）"""
    return get_config("last_decay_date", None)


# ─── 角色枚举工具 ───

def _enumerate_character_ids() -> list:
    """枚举所有有数据的角色 ID：characters_v2 表 ∪ data/chats/char_* 目录 ∪ 默认 0"""
    char_ids = set()
    try:
        from core.character_card import CharacterCard
        for c in CharacterCard.list_all():
            cid = c.get("id", 0) if isinstance(c, dict) else getattr(c, "id", 0)
            if cid:
                char_ids.add(cid)
    except Exception as e:
        silent_exc("enumerate_chars.table", e)
    try:
        import os
        chats_dir = os.path.join("data", "chats")
        if os.path.isdir(chats_dir):
            for entry in os.listdir(chats_dir):
                if entry.startswith("char_"):
                    try:
                        cid = int(entry[5:])
                        char_ids.add(cid)
                    except ValueError:
                        pass
    except Exception as e:
        silent_exc("enumerate_chars.dir_scan", e)
    char_ids.add(0)  # 永远包含默认角色
    return sorted(char_ids)


# ─── 每日演化主入口 ───

def process_daily_evolution():
    """每日触发一次。对每个角色执行所有时间维度演化规则。

    全局调度状态（last_evolution_date）在主库 config，一天只跑一次。
    OCEAN 五维、relationship、emotion_log 全部 per-character，所以每条规则都按角色遍历。
    """
    today = datetime.now().strftime("%Y-%m-%d")
    if not _try_claim_evolution_date(today):
        return

    logger.info(f"[情绪演化] 开始每日演化检查 ({today})")
    hours_since = _get_hours_since_last_interaction()
    char_ids = _enumerate_character_ids()
    logger.info(f"[情绪演化] 待演化角色: {char_ids}")

    for cid in char_ids:
        try:
            _check_sustained_low_mood(cid)
            _rule_silence_decay(hours_since, cid)
            _rule_cold_adaptation(cid)
            _rule_habitual_closeness(cid)
            _rule_interaction_quality(cid)
            _rule_sarcasm_penalty(cid)
            # 每日互动 → agreeableness 微增（让用户感知系统在运行）
            try:
                from core.emotion_tracker import get_emotion_trend
                today_trend = get_emotion_trend(1, cid)
                if today_trend and today_trend[0]["total_messages"] > 0:
                    update_trait("agreeableness", 0.01, cid)
            except Exception as e:
                silent_exc(f"daily_evolution.interaction.char_{cid}", e)
            # 周日反思
            if datetime.now().weekday() == 6:
                _rule_weekly_reflection(cid)
        except Exception as e:
            silent_exc(f"daily_evolution.char_{cid}", e)

    _set_last_evolution_date(today)
    # 清理 90 天前的旧日志（每个角色库各自清）
    for cid in char_ids:
        try:
            with get_chat_conn(cid) as conn:
                conn.cursor().execute("DELETE FROM emotion_log WHERE timestamp < date('now', '-90 days')")
        except Exception as e:
            silent_exc(f"daily_evolution.cleanup.char_{cid}", e)
    logger.info(f"[情绪演化] 每日演化完成，覆盖 {len(char_ids)} 个角色")


# ─── 演化规则 ───

def _check_sustained_low_mood(character_id: int = 0):
    """检测用户情绪是否持续低落 >= 3 天。若是，写 proactive_flag 供主动触发 C 读取。"""
    from core.emotion_tracker import get_emotion_trend
    from core.db import set_proactive_flag, get_proactive_flag
    trend = get_emotion_trend(7, character_id)
    if len(trend) < 3:
        return

    consecutive_negative = 0
    for d in reversed(trend):
        if d["score"] < -3:
            consecutive_negative += 1
        else:
            break

    flag_key = f"sustained_low_mood_char_{character_id}"
    days_key = f"low_mood_consecutive_days_char_{character_id}"
    if consecutive_negative >= 3:
        existing = get_proactive_flag(flag_key)
        if not existing or existing != datetime.now().strftime("%Y-%m-%d"):
            set_proactive_flag(flag_key, datetime.now().strftime("%Y-%m-%d"))
            set_proactive_flag(days_key, str(consecutive_negative))
            logger.info(f"[情绪演化] 角色{character_id} 检测到持续低落 {consecutive_negative} 天")
    else:
        existing = get_proactive_flag(flag_key)
        if existing:
            set_proactive_flag(flag_key, "")
            set_proactive_flag(days_key, "")
            logger.info(f"[情绪演化] 角色{character_id} 情绪已恢复")


def _rule_silence_decay(hours_since: float | None, character_id: int = 0):
    """沉默衰减：连续 3+ 天无互动 → affection -0.2/天，trust -0.1/天（最多10天递减）
    增量计算：仅衰减自上次演化以来的天数。"""
    if hours_since is None:
        return
    days = hours_since / 24
    if days < 3:
        return

    last_decay = _get_last_decay_date()
    if last_decay:
        try:
            last = datetime.fromisoformat(last_decay)
            days_since_last = (datetime.now() - last).days
        except (ValueError, TypeError):
            days_since_last = 1
    else:
        days_since_last = 1
    effective_days = min(days_since_last, 10)

    if effective_days <= 0:
        return

    affection_loss = -0.2 * effective_days
    trust_loss = -0.1 * effective_days

    _update_relationship_value("affection", affection_loss, character_id)
    _update_relationship_value("trust", trust_loss, character_id)

    _log_evolution_event(
        "time_decay",
        f"用户沉默{int(days)}天，好感-{abs(affection_loss):.1f}，信任-{abs(trust_loss):.1f}",
        affection_loss, trust_loss, character_id,
    )

    set_config("last_decay_date", datetime.now().strftime("%Y-%m-%d"))

    if days > 7:
        update_trait("conscientiousness", -0.05, character_id)

    logger.info(f"[情绪演化] 角色{character_id} 沉默衰减: {int(days)}天(增量{effective_days}天) → affection{affection_loss:+.1f} trust{trust_loss:+.1f}")


def _rule_cold_adaptation(character_id: int = 0):
    """冷淡适应：用户情绪偏负面占比高 → extraversion -0.05，agreeableness -0.03"""
    from core.emotion_tracker import get_emotion_trend
    trend = get_emotion_trend(7, character_id)
    if len(trend) < 2:
        return

    negative_days = sum(1 for d in trend if d["score"] < -5)
    total_days = len(trend)
    neg_ratio = negative_days / total_days if total_days > 0 else 0
    if neg_ratio > 0.5:
        update_trait("extraversion", -0.05, character_id)
        update_trait("agreeableness", -0.03, character_id)
        _log_evolution_event(
            "autonomous_adaptation",
            f"用户{negative_days}天情绪负面（占比{neg_ratio:.0%}），AI进入自我保护状态",
            0, 0, character_id,
        )
        logger.info(f"[情绪演化] 角色{character_id} 冷淡适应: 负面占比{neg_ratio:.0%} → extraversion-0.05")


def _rule_habitual_closeness(character_id: int = 0):
    """习惯亲近：近期频繁互动 → 信任缓慢积累"""
    from core.emotion_tracker import get_emotion_trend
    trend = get_emotion_trend(7, character_id)
    if len(trend) < 3:
        return

    active_days = sum(1 for d in trend if d["total_messages"] > 0)
    if active_days >= 3:
        _update_relationship_value("trust", 0.05, character_id)
        _log_evolution_event(
            "habitual_closeness",
            f"近{len(trend)}天有{active_days}天互动，习惯成自然",
            0, 0.05, character_id,
        )
        logger.info(f"[情绪演化] 角色{character_id} 习惯亲近: {active_days}/{len(trend)}天有互动 → trust+0.05")


def _rule_interaction_quality(character_id: int = 0):
    """互动质量驱动的 trait 微调：基于最近 10 条消息的实时情感强度加权。

    命中高权重 mention 的消息 intensity × 1.5。
    """
    from core.emotion_patterns import detect_emotion_intensity

    try:
        with get_chat_conn(character_id) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content FROM chat_history WHERE role='user' ORDER BY id DESC LIMIT 10"
            )
            msgs = [r[0] for r in cursor.fetchall() if r[0]]

        if not msgs:
            return

        top_mentions = set()
        try:
            from core.mention_tracker import get_top_mentions
            for m in get_top_mentions(n=15, min_weight=0.3, character_id=character_id):
                top_mentions.add(m["phrase"])
        except Exception:
            pass

        positive_intensity = 0.0
        negative_intensity = 0.0
        for m in msgs:
            emo, intensity = detect_emotion_intensity(m)
            if top_mentions:
                try:
                    import jieba
                    m_phrases = {w for w in jieba.cut(m) if len(w) >= 2}
                    if m_phrases & top_mentions:
                        intensity *= 1.5
                except Exception:
                    pass
            if emo in ('happy', 'love', 'surprise'):
                positive_intensity += intensity
            elif emo == 'sad':
                negative_intensity += intensity

        total = positive_intensity + negative_intensity
        if total == 0:
            return

        positive_ratio = positive_intensity / total

        if positive_ratio > 0.6:
            update_trait("openness", 0.02 * positive_ratio, character_id)
            update_trait("extraversion", 0.015 * positive_ratio, character_id)
            update_trait("neuroticism", -0.01 * positive_ratio, character_id)
            logger.info(f"[情绪演化] 角色{character_id} 互动质量：正面占比{positive_ratio:.0%} → openness/extraversion+")

        if positive_ratio < 0.4:
            update_trait("neuroticism", 0.02 * (1 - positive_ratio), character_id)
            logger.info(f"[情绪演化] 角色{character_id} 互动质量：负面主导 → neuroticism+")

    except Exception as e:
        silent_exc("_rule_interaction_quality", e)


def _rule_sarcasm_penalty(character_id: int = 0):
    """反讽惩罚：每 50 条消息扫描用户反讽率，过高 → agreeableness 微降"""
    from core.emotion_patterns import is_sarcastic

    try:
        with get_chat_conn(character_id) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content FROM chat_history WHERE role='user' ORDER BY id DESC LIMIT 50"
            )
            msgs = [r[0] for r in cursor.fetchall() if r[0]]

        if not msgs or len(msgs) < 10:
            return

        sarc_count = sum(1 for m in msgs if is_sarcastic(m))
        sarc_ratio = sarc_count / len(msgs)

        if sarc_ratio > 0.2:
            delta = -0.02 * (sarc_ratio * 5)
            delta = max(-0.1, delta)
            update_trait("agreeableness", delta, character_id)
            logger.info(f"[情绪演化] 角色{character_id} 反讽惩罚：反讽率{sarc_ratio:.0%} → agreeableness{delta:+.3f}")
    except Exception as e:
        silent_exc("_rule_sarcasm_penalty", e)


def _rule_weekly_reflection(character_id: int = 0):
    """周日反思：综合本周互动质量，微调所有 traits"""
    from core.emotion_tracker import get_emotion_trend
    trend = get_emotion_trend(7, character_id)

    positive_days = sum(1 for d in trend if d["score"] > 5)
    negative_days = sum(1 for d in trend if d["score"] < -5)
    has_deep_chat = any(d["total_messages"] > 30 for d in trend)

    adjust_log = []

    if positive_days >= 4:
        update_trait("extraversion", 0.05, character_id)
        adjust_log.append("extraversion+0.05")
        if has_deep_chat:
            update_trait("agreeableness", 0.03, character_id)
            adjust_log.append("agreeableness+0.03")

    if negative_days >= 4:
        update_trait("extraversion", -0.05, character_id)
        adjust_log.append("extraversion-0.05")

    total_msgs = sum(d["total_messages"] for d in trend)
    if total_msgs > 100:
        update_trait("conscientiousness", 0.03, character_id)
        adjust_log.append("conscientiousness+0.03")

    if adjust_log:
        summary = f"周日反思：本周{'正面为主' if positive_days >= 4 else '负面为主' if negative_days >= 4 else '平稳'}，" + "，".join(adjust_log)
        _log_evolution_event("weekly_reflection", summary, 0, 0, character_id)
        logger.info(f"[情绪演化] 角色{character_id} {summary}")


# ─── 前端数据接口 ───

def get_trait_profile(character_id: int = 0) -> dict:
    """获取 AI 性格画像（含文字描述）"""
    traits = get_all_traits(character_id)
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

    ai_name = get_config("ai_name", "夕语")
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


def get_emotion_timeline(days: int = 30, character_id: int = 0) -> dict:
    """返回前端图表所需的时间线数据（包含好感/信任历史曲线）"""
    from core.emotion_tracker import get_emotion_trend

    daily_emotion = get_emotion_trend(days, character_id)
    start = (datetime.now() - timedelta(days=days)).isoformat()

    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT timestamp, event_type, reason, affection_delta, trust_delta, ai_emotion_after FROM emotion_log WHERE timestamp >= ? ORDER BY timestamp ASC LIMIT 100",
            (start,)
        )
        events = [dict(r) for r in cursor.fetchall()]

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

    # 当天数据用当前实际值
    from core.relationship import get_relationship
    cur_aff, cur_trust = get_relationship(character_id)
    today = datetime.now().strftime("%Y-%m-%d")
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
