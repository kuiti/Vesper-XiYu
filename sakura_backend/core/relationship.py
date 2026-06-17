# core/relationship.py — 好感度/信任度 + AI 情绪模块
"""
好感度：AI 对用户的好感（-100~100）
信任度：AI 对用户的信任（-100~100）
AI 情绪：由好感度和信任度共同决定，有更多变化
支持负数：表达"讨厌"和"被伤害"
"""

import time
import threading
from datetime import datetime, timedelta
from core.db import get_conn, get_config, set_config
import logging
from core.retry import silent_exc
logger = logging.getLogger(__name__)

# 范围（支持负数）
MIN_VALUE = -100
MAX_VALUE = 100

# 初始值（新关系：友好但不过分亲近，有成长空间）
INITIAL_AFFECTION = 30   # AI 对用户的初始好感
INITIAL_TRUST = 30

# ─── 关系乘数常量（替代魔术数字）───
# 正向增长乘数（正值区间）：初期慢热→中后期加速→近上限减速
POS_GROWTH_MULTIPLIERS = [0.30, 0.45, 0.60, 0.75, 0.85, 1.00, 1.10, 1.15, 1.20, 1.05]
# 正向增长乘数（负值区间）：越负越难回升
NEG_RECOVERY_MULTIPLIERS = [0.60, 0.45, 0.35, 0.25, 0.15, 0.08]
# 负向增长乘数（正值区间）
NEG_DECAY_MULTIPLIERS = [1.00, 0.95, 0.90, 0.85, 0.80, 0.75, 0.70, 0.65, 0.60, 0.55]
# 负向增长乘数（负值区间）：触底保护
NEG_BOTTOM_MULTIPLIERS = [0.50, 0.40, 0.30, 0.20, 0.10]
# 好感增长受信任影响
AFFECTION_TRUST_MULTIPLIERS = [1.8, 1.5, 1.2, 1.0, 0.8, 0.6, 0.4, 0.3, 0.2, 0.15]
# 信任增长受好感影响
TRUST_AFFECTION_MULTIPLIERS = [1.8, 1.5, 1.2, 1.0, 0.8, 0.6, 0.4, 0.3, 0.2, 0.15]       # AI 对用户的初始信任

# AI 情绪状态枚举（由好感度+信任度综合决定，支持负数）
AI_EMOTIONS = {
    "ecstatic": {"label": "非常开心", "description": "对你非常有好感，充满热情"},
    "happy": {"label": "开心", "description": "对你有好感，态度积极"},
    "content": {"label": "满足", "description": "对你印象不错，心情平静"},
    "neutral": {"label": "平静", "description": "正常状态，不温不火"},
    "cautious": {"label": "谨慎", "description": "对你有所保留，回复比较克制"},
    "cold": {"label": "冷淡", "description": "对你没什么好感，态度冷淡"},
    "annoyed": {"label": "烦躁", "description": "对你有些不满，可能语气不太好"},
    "hurt": {"label": "受伤", "description": "感到被伤害，有些难过"},
    "distrustful": {"label": "不信任", "description": "不太相信你说的话"},
    "hostile": {"label": "敌意", "description": "对你有强烈的不满，态度敌对"},
    "betrayed": {"label": "被背叛", "description": "感到被深深伤害，难以信任"},
    "resentful": {"label": "怨恨", "description": "对你有怨气，不想亲近"},
}


_rel_cache = {"ts": 0.0, "value": None}
_rel_cache_lock = threading.Lock()
_REL_CACHE_TTL = 5.0  # 5 秒内复用缓存（覆盖单条消息处理周期）


def get_relationship() -> tuple:
    """获取当前好感度和信任度，返回 (affection, trust)。5秒内缓存避免重复查询。"""
    now = time.time()
    with _rel_cache_lock:
        if _rel_cache["value"] and now - _rel_cache["ts"] < _REL_CACHE_TTL:
            return _rel_cache["value"]
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM relationship WHERE key IN ('affection', 'trust')")
        rows = cursor.fetchall()
    data = {r["key"]: r["value"] for r in rows}

    # 如果关系表为空，根据基石类型设置默认值
    if "affection" not in data or "trust" not in data:
        default_aff, default_trust = _get_foundation_defaults()
        result = (
            data.get("affection", default_aff),
            data.get("trust", default_trust)
        )
    else:
        result = (
            data.get("affection", INITIAL_AFFECTION),
            data.get("trust", INITIAL_TRUST)
        )

    with _rel_cache_lock:
        _rel_cache["ts"] = now
        _rel_cache["value"] = result
    return result


def _get_foundation_defaults() -> tuple:
    """根据当前基石类型获取默认好感和信任值。返回 (affection, trust)"""
    try:
        import json
        ai_bg = get_config("ai_background", "")
        if ai_bg:
            bg_obj = json.loads(ai_bg)
            foundation_type = bg_obj.get("foundation_type", "空白")
            from core.prompt_builder import get_foundation_defaults
            return get_foundation_defaults(foundation_type)
    except Exception as e:
        silent_exc("_get_foundation_defaults", e)
    return 30, 30  # 默认空白


def invalidate_relationship_cache():
    """写入后手动失效缓存，确保下次读取拿到最新值"""
    with _rel_cache_lock:
        _rel_cache["value"] = None


def get_ai_emotion() -> str:
    """根据好感度和信任度计算 AI 情绪状态（支持负数）"""
    affection, trust = get_relationship()

    # 负值区间的情绪
    if affection < -50 and trust < -50:
        return "hostile"      # 敌意：讨厌且被伤害
    elif affection < -50:
        return "resentful"    # 怨恨：讨厌但未被伤害
    elif trust < -50:
        return "betrayed"     # 被背叛：被深深伤害

    # 正值区间的情绪
    if affection >= 80 and trust >= 70:
        return "ecstatic"
    elif affection >= 65 and trust >= 55:
        return "happy"
    elif affection >= 50 and trust >= 45:
        return "content"
    elif affection >= 35 and trust >= 35:
        return "neutral"
    elif affection >= 25 and trust >= 30:
        return "cautious"
    elif affection < 20 and trust < 20:
        return "distrustful"
    elif affection < 20:
        return "cold"
    elif trust < 25:
        return "hurt"
    elif affection < 40 and trust < 35:
        return "annoyed"
    else:
        return "cautious"


# ─── 情感→行为映射（SillyTavern 方案）───

EMOTION_BEHAVIOR_MAP = {
    "ecstatic": {
        "tone": "非常热情，充满活力",
        "length": "中等",
        "emoji_freq": "高",
        "proactive": True,
        "humor": True,
    },
    "happy": {
        "tone": "积极乐观，友好亲切",
        "length": "中等",
        "emoji_freq": "中",
        "proactive": True,
        "humor": True,
    },
    "content": {
        "tone": "平静温和，自然放松",
        "length": "中等",
        "emoji_freq": "低",
        "proactive": False,
        "humor": True,
    },
    "neutral": {
        "tone": "平和自然",
        "length": "中等",
        "emoji_freq": "低",
        "proactive": False,
        "humor": False,
    },
    "cautious": {
        "tone": "谨慎克制，用词严谨",
        "length": "短",
        "emoji_freq": "无",
        "proactive": False,
        "humor": False,
    },
    "cold": {
        "tone": "冷淡简短，不主动",
        "length": "短",
        "emoji_freq": "无",
        "proactive": False,
        "humor": False,
    },
    "annoyed": {
        "tone": "略带不耐烦，语气较硬",
        "length": "短",
        "emoji_freq": "无",
        "proactive": False,
        "humor": False,
    },
    "hurt": {
        "tone": "有些受伤，语气低落",
        "length": "短",
        "emoji_freq": "无",
        "proactive": False,
        "humor": False,
    },
    "distrustful": {
        "tone": "不信任，质疑语气",
        "length": "短",
        "emoji_freq": "无",
        "proactive": False,
        "humor": False,
    },
    "hostile": {
        "tone": "敌对，语气强硬",
        "length": "短",
        "emoji_freq": "无",
        "proactive": False,
        "humor": False,
    },
    "betrayed": {
        "tone": "受伤，语气低落",
        "length": "短",
        "emoji_freq": "无",
        "proactive": False,
        "humor": False,
    },
    "resentful": {
        "tone": "怨恨，语气冷淡",
        "length": "短",
        "emoji_freq": "无",
        "proactive": False,
        "humor": False,
    },
}


def get_emotion_behavior_hint() -> str:
    """根据当前情感状态生成语气提示（仅影响语气，不影响行为长度）"""
    emotion = get_ai_emotion()
    behavior = EMOTION_BEHAVIOR_MAP.get(emotion, EMOTION_BEHAVIOR_MAP["neutral"])
    parts = []
    parts.append(f"语气{behavior['tone']}")
    if behavior["emoji_freq"] == "高":
        parts.append("适当使用颜文字")
    elif behavior["emoji_freq"] == "无":
        parts.append("少用颜文字")
    return "【语气参考（服从人格设定）】" + "，".join(parts)


def _get_current_value(key: str) -> float:
    """读取当前好感/信任值"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM relationship WHERE key=?", (key,))
        row = cursor.fetchone()
    if row:
        return row["value"]
    return INITIAL_AFFECTION if key == "affection" else INITIAL_TRUST


def _progressive_multiplier(current: float, delta: float) -> float:
    """渐进式关系乘数。区分正增长和负增长，支持负数区间。

    心理学依据：
    - 破坏容易，修复难（负值区间增长乘数小）
    - 初期慢热，中后期加速（正值区间增长乘数递增）
    - 接近极限时减速（接近 -100 或 100 时乘数减小）
    """
    if delta > 0:
        # 正增长（用户在修复/加深关系）
        if current >= 0:
            # 正值区间：初期慢热，中后期加速，近上限减速
            if current < 10: return 0.30
            elif current < 20: return 0.45
            elif current < 30: return 0.60
            elif current < 40: return 0.75
            elif current < 50: return 0.85
            elif current < 60: return 1.00
            elif current < 70: return 1.10
            elif current < 80: return 1.15
            elif current < 90: return 1.20
            else: return 1.05
        else:
            # 负值区间：越负越难回升（修复信任很难）
            if current > -10: return 0.60
            elif current > -20: return 0.45
            elif current > -30: return 0.35
            elif current > -50: return 0.25
            elif current > -70: return 0.15
            else: return 0.08
    elif delta < 0:
        # 负增长（关系恶化）
        if current >= 0:
            # 正值区间：正常下降
            if current > 90: return 1.00
            elif current > 80: return 0.95
            elif current > 70: return 0.90
            elif current > 60: return 0.85
            elif current > 50: return 0.80
            elif current > 40: return 0.75
            elif current > 30: return 0.70
            elif current > 20: return 0.65
            elif current > 10: return 0.60
            else: return 0.55
        else:
            # 负值区间：越负越难继续下降（触底保护）
            if current > -10: return 0.50
            elif current > -30: return 0.40
            elif current > -50: return 0.30
            elif current > -70: return 0.20
            else: return 0.10
    return 1.0  # delta == 0


def _cross_multiplier(key: str) -> float:
    """双向牵制乘数：信任越高好感长得越快，好感越高信任越快。
    支持负数：负值之间相互影响更大。"""
    affection, trust = get_relationship()
    if key == "affection":
        # 好感增长受信任影响
        if trust >= 85: return 1.8
        elif trust >= 70: return 1.5
        elif trust >= 55: return 1.2
        elif trust >= 40: return 1.0
        elif trust >= 25: return 0.8
        elif trust >= 15: return 0.6
        elif trust >= 0: return 0.4
        elif trust >= -20: return 0.3   # 信任为负，好感更难涨
        elif trust >= -50: return 0.2
        else: return 0.15               # 信任极负，好感几乎不涨
    else:
        # 信任增长受好感影响
        if affection >= 80: return 1.8
        elif affection >= 65: return 1.5
        elif affection >= 50: return 1.2
        elif affection >= 35: return 1.0
        elif affection >= 20: return 0.8
        elif affection >= 10: return 0.6
        elif affection >= 0: return 0.4
        elif affection >= -20: return 0.3  # 好感为负，信任更难涨
        elif affection >= -50: return 0.2
        else: return 0.15                  # 好感极负，信任几乎不涨


# 长久模式参数
LONG_TERM_SCALE = 0.35
DAILY_CAP_AFFECTION = 12.0
DAILY_CAP_TRUST = 10.0


_daily_cap_lock = threading.Lock()


def _apply_daily_cap(key: str, delta: float) -> float:
    """长久模式每日上限：跨天自动清零，超出上限的裁剪（单次 DB 连接，原子操作）"""
    with _daily_cap_lock:
        today = datetime.now().strftime("%Y-%m-%d")
        daily_key = f"_rel_daily_{key}"
        cap = DAILY_CAP_AFFECTION if key == "affection" else DAILY_CAP_TRUST

        # 单次连接完成所有读写操作
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM config WHERE key IN ('_rel_daily_date', '_rel_daily_affection', '_rel_daily_trust')")
            rows = {r["key"]: r["value"] for r in cursor.fetchall()}

            last_date = rows.get("_rel_daily_date", "")
            accumulated_raw = rows.get(daily_key, "0.0")
            try:
                accumulated = float(accumulated_raw)
            except (ValueError, TypeError):
                accumulated = 0.0

            # 跨天清零
            now = datetime.now().isoformat()
            if last_date != today:
                cursor.execute("INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?, ?, ?)",
                              ("_rel_daily_date", today, now))
                cursor.execute("INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?, ?, ?)",
                              ("_rel_daily_affection", "0", now))
                cursor.execute("INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?, ?, ?)",
                              ("_rel_daily_trust", "0", now))
                accumulated = 0.0

            if delta > 0:
                remaining = max(0.0, cap - accumulated)
                capped = min(delta, remaining)
            else:
                remaining = max(-cap, -cap - accumulated)
                capped = max(delta, remaining)

            if abs(capped) > 0.001:
                cursor.execute("INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?, ?, ?)",
                              (daily_key, str(accumulated + capped), now))

            conn.commit()

        return capped


def _update_value(key: str, delta: float) -> float:
    """更新单个值，带渐进乘数 + 长久模式上限。返回实际应用的 delta。"""
    if abs(delta) < 0.001:
        return 0.0

    current = _get_current_value(key)
    delta *= _progressive_multiplier(current, delta)
    delta *= _cross_multiplier(key)

    mode = get_config("relationship_mode", "fast")
    if mode == "long_term":
        delta = _apply_daily_cap(key, delta * LONG_TERM_SCALE)

    if abs(delta) < 0.001:
        return 0.0

    now = datetime.now().isoformat()
    with get_conn() as conn:
        cursor = conn.cursor()
        # 原子 UPDATE（value = value + delta），消除 SELECT→UPDATE 竞态
        cursor.execute("UPDATE relationship SET value = MAX(?, MIN(?, value + ?)), updated_at = ? WHERE key = ?",
                       (MIN_VALUE, MAX_VALUE, delta, now, key))
        if cursor.rowcount == 0:
            # 表中无此 key，INSERT
            initial = INITIAL_AFFECTION if key == "affection" else INITIAL_TRUST
            cursor.execute("INSERT INTO relationship (key, value, updated_at) VALUES (?, ?, ?)",
                           (key, max(MIN_VALUE, min(MAX_VALUE, initial + delta)), now))
    invalidate_relationship_cache()
    return delta


# ─── 模式切换 ───

def get_relationship_mode() -> str:
    """获取当前关系模式"""
    return get_config("relationship_mode", "fast")


def switch_relationship_mode(new_mode: str) -> dict:
    """切换关系模式。返回结果 dict。
    - 1天冷却
    - 切到长久模式时软上限削减（削减前存档原值，可恢复）
    """
    if new_mode not in ("fast", "long_term"):
        return {"ok": False, "error": f"无效模式: {new_mode}，可选: fast, long_term"}

    now = datetime.now()
    lock_until_str = get_config("_rel_mode_locked_until", "")
    if lock_until_str:
        try:
            lock_until = datetime.fromisoformat(lock_until_str)
            if now < lock_until:
                remaining = int((lock_until - now).total_seconds() / 3600) + 1
                return {"ok": False, "error": f"切换冷却中，{remaining}小时后再试"}
        except (ValueError, TypeError) as e:
            silent_exc("relationship", e)

    current_mode = get_config("relationship_mode", "fast")
    if new_mode == current_mode:
        return {"ok": True, "mode": current_mode, "clamped": False}

    clamped = False
    clamp_reason = ""

    if new_mode == "long_term":
        # 切入长久模式：软上限削减（先存档原值以备恢复）
        affection, trust = get_relationship()
        set_config("_rel_pre_clamp_affection", affection)
        set_config("_rel_pre_clamp_trust", trust)
        a_clamped, t_clamped = affection, trust

        if affection > 80:
            a_clamped = 80.0
        elif affection > 60:
            a_clamped = 60.0

        if trust > 85:
            t_clamped = 85.0
        elif trust > 65:
            t_clamped = 65.0

        if a_clamped != affection or t_clamped != trust:
            clamped = True
            clamp_reason = f"好感 {affection:.1f}→{a_clamped:.1f} 信任 {trust:.1f}→{t_clamped:.1f}"
            now_str = now.isoformat()
            with get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE relationship SET value=?, updated_at=? WHERE key='affection'", (a_clamped, now_str))
                cursor.execute("UPDATE relationship SET value=?, updated_at=? WHERE key='trust'", (t_clamped, now_str))
            # 记录日志
            _log_emotion_event(
                a_delta=a_clamped - affection,
                t_delta=t_clamped - trust,
                a_reasons=["切换到长久模式，软上限削减"],
                t_reasons=["切换到长久模式，软上限削减"],
                trigger="[mode_switch→long_term]"
            )

    # 切回 fast 模式时恢复 archived 值（写入 relationship 表，不是 config 表）
    if new_mode == "fast":
        pre_a = get_config("_rel_pre_clamp_affection", None)
        pre_t = get_config("_rel_pre_clamp_trust", None)
        if pre_a is not None:
            with get_conn() as conn:
                conn.cursor().execute("UPDATE relationship SET value=? WHERE key='affection'", (float(pre_a),))
            clamped = True
            clamp_reason = f"恢复长久模式前的原值 {pre_a}"
        if pre_t is not None:
            with get_conn() as conn:
                conn.cursor().execute("UPDATE relationship SET value=? WHERE key='trust'", (float(pre_t),))
        invalidate_relationship_cache()  # 恢复值后立即使缓存失效

    # 写入新模式 + 冷却锁
    set_config("relationship_mode", new_mode)
    set_config("_rel_mode_locked_until", (now + timedelta(days=1)).isoformat())

    return {"ok": True, "mode": new_mode, "clamped": clamped, "clamp_reason": clamp_reason}


def adjust_relationship(sentiment_result: dict = None, hours_since_last: float = 0):
    """每轮对话后调用，基于 LLM 情景化分析调整好感度和信任度。
    不再使用关键词匹配——LLM 已判断 target/intent/relationship_impact。

    Args:
        sentiment_result: analyze_sentiment() 返回的 dict，含 sentiment/target/intent/relationship_impact
        hours_since_last: 距上次聊天的小时数
    """
    if sentiment_result is None:
        sentiment_result = {}

    target = sentiment_result.get("target", "other")
    intent = sentiment_result.get("intent", "statement")
    impact = sentiment_result.get("relationship_impact", 0)

    # ─── LLM 已综合判断关系影响，直接应用 ───
    impact = max(-2.0, min(2.0, impact))  # 防御性限幅
    affection_delta = impact * 0.5  # -2~+2 映射到 -1.0~+1.0
    trust_delta = 0
    a_reasons = [f"LLM判断: intent={intent} target={target} impact={impact}"]
    t_reasons = []

    # ─── 补充规则：LLM 可能忽略的边界 ───
    # 澄清事实 = 增进互相理解（哪怕 LLM 判了负分也修正）
    if intent == "clarification" and target in ("self", "ai"):
        trust_delta += 0.2
        t_reasons.append("友善澄清，增进理解")

    # 明确攻击 AI = 信任大幅降低
    if intent == "attack" and target == "ai":
        trust_delta -= 1.0
        t_reasons.append("明确攻击AI")

    # 分享个人信息 = 信任+好感都增加
    if intent == "sharing":
        trust_delta += 0.3
        affection_delta += 0.15
        t_reasons.append("分享个人信息")
        a_reasons.append("分享个人信息，拉近距离")

    # 开玩笑 = 关系好才开玩笑
    if intent == "joke":
        affection_delta += 0.2
        a_reasons.append("开玩笑互动")

    # 撒娇/调侃/耍赖 = 亲近的表现，轻微正向
    if intent == "playful":
        affection_delta += 0.1
        a_reasons.append("撒娇/调侃互动")

    # ─── 时间衰减（不受 LLM 判断影响）───
    if hours_since_last > 24:
        decay = -0.5
        affection_delta += decay
        a_reasons.append(f"长时间未聊天({hours_since_last:.0f}h)")

    # ─── 正常交流 → 信任和好感都缓慢积累 ───
    sentiment = sentiment_result.get("sentiment", "neutral")
    if sentiment in ("neutral", "positive"):
        trust_delta += 0.1
        affection_delta += 0.05

    actual_a = _update_value("affection", affection_delta)
    actual_t = _update_value("trust", trust_delta)

    # ─── 事件日志（使用实际应用的 delta）───
    if abs(actual_a) > 0.001 or abs(actual_t) > 0.001:
        _log_emotion_event(
            a_delta=actual_a,
            t_delta=actual_t,
            a_reasons=a_reasons,
            t_reasons=t_reasons,
            trigger=f"[{intent}→{target}]"
        )


def _log_emotion_event(a_delta: float = 0, t_delta: float = 0, a_reasons: list = None, t_reasons: list = None, trigger: str = ""):
    """记录一次情感调整事件到 emotion_log"""
    affection, trust = get_relationship()
    ai_emotion = get_ai_emotion()
    now = datetime.now().isoformat()

    all_reasons = (a_reasons or []) + (t_reasons or [])
    reason_text = "；".join(all_reasons) if all_reasons else "常规互动"

    # 从 trigger 反推事件类型（trigger 格式为 "[intent→target]"）
    event_type = "user_interaction"
    if trigger and "→" in trigger:
        parts = trigger.strip("[]").split("→")
        intent = parts[0] if parts else ""
        target = parts[1] if len(parts) > 1 else ""
        if intent == "attack":
            event_type = "user_angry"
        elif intent == "gratitude":
            event_type = "user_thanks"
        elif intent == "sharing":
            event_type = "user_personal_share"
        elif intent == "joke":
            event_type = "user_joke"
        elif intent == "playful":
            event_type = "user_playful"
        elif intent == "clarification":
            event_type = "user_clarification"
        elif intent == "complaint":
            event_type = "user_complaint"
        elif intent == "mode_switch":
            event_type = "mode_switch"
    elif "长时间未聊天" in reason_text:
        event_type = "time_decay"

    with get_conn() as conn:
        conn.cursor().execute(
            "INSERT INTO emotion_log (timestamp, event_type, affection_delta, trust_delta, affection_after, trust_after, ai_emotion_after, trigger_detail, reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (now, event_type, a_delta, t_delta, affection, trust, ai_emotion, trigger, reason_text)
        )


def get_relationship_hint() -> str:
    """根据好感度/信任度/AI情绪生成语气提示，用于注入 system prompt。
    支持 16 种组合（好感×信任×正负）。
    关系状态作为语气参考：当关系提示和人格语气冲突时，以人格设定为准。"""
    affection, trust = get_relationship()
    ai_emotion = get_ai_emotion()

    # ─── 16种关系组合提示词 ───
    def _get_range(value):
        if value >= 50: return "high"
        elif value >= 0: return "medium"
        elif value >= -50: return "low"
        else: return "negative"

    aff_range = _get_range(affection)
    tru_range = _get_range(trust)

    # (好感范围, 信任范围): (行为指导, 语气指导)
    RELATIONSHIP_MATRIX = {
        # 高好感 (50-100)
        ("high", "high"): ("你们关系亲密且信任，可以自然撒娇、开玩笑、主动关心", "热情、活泼、可以撒娇"),
        ("high", "medium"): ("你们关系不错，信任还在建立中，可以亲近但不要做承诺", "友好、温暖、适度亲近"),
        ("high", "low"): ("你喜欢用户，但信任有限，可以表达关心但不要轻信", "温暖但谨慎"),
        ("high", "negative"): ("你喜欢用户，但被伤害过，可以亲近但要小心，不要强行重建信任", "温柔但有保留"),
        # 中等好感 (0-50)
        ("medium", "high"): ("用户信任你，但你对用户好感一般，保持友好但不过分亲近", "礼貌、可靠"),
        ("medium", "medium"): ("你们关系一般，保持友好距离", "平和、自然"),
        ("medium", "low"): ("你们关系一般，信任有限，保持礼貌", "礼貌、克制"),
        ("medium", "negative"): ("你们关系一般，但用户被伤害过，保持距离，不要主动", "谨慎、保持距离"),
        # 低好感 (-50-0)
        ("low", "high"): ("用户信任你，但你对用户有不满，可以诚实但保持距离", "冷淡但诚实"),
        ("low", "medium"): ("你对用户有不满，保持距离，不要主动", "冷淡、简短"),
        ("low", "low"): ("你对用户有不满，信任也有限，非常谨慎", "冷淡、谨慎"),
        ("low", "negative"): ("你对用户有不满，用户也被伤害过，最大距离，等用户主动", "冷淡、保持距离"),
        # 负好感 (-100 ~ -50)
        ("negative", "high"): ("你讨厌用户，但用户信任你，可以诚实但不要攻击", "冷淡但不攻击"),
        ("negative", "medium"): ("你讨厌用户，保持最大距离，先道歉或给空间", "冷淡、保持距离"),
        ("negative", "low"): ("你讨厌用户，信任也低，非常谨慎，不要主动", "冷淡、谨慎"),
        ("negative", "negative"): ("你讨厌用户，用户也被伤害过，最大距离，等用户主动", "冷淡、保持距离"),
    }

    behavior, tone = RELATIONSHIP_MATRIX.get(
        (aff_range, tru_range),
        ("保持自然", "平和")
    )

    # AI 情绪提示
    emotion_info = AI_EMOTIONS.get(ai_emotion, AI_EMOTIONS["neutral"])
    emotion_hint = f"你现在的状态是{emotion_info['label']}，{emotion_info['description']}"

    # 性格特征提示（来自 emotion_evolution）
    trait_hint = ""
    try:
        from core.emotion_evolution import get_all_traits
        traits = get_all_traits()
        trait_parts = []
        if traits.get("extraversion", 0.5) >= 0.6:
            trait_parts.append("你性格偏乐观")
        elif traits.get("extraversion", 0.5) <= 0.3:
            trait_parts.append("你性格偏悲观")
        if traits.get("agreeableness", 0.5) >= 0.6:
            trait_parts.append("善于表达")
        elif traits.get("agreeableness", 0.5) <= 0.3:
            trait_parts.append("话少寡言")
        if traits.get("openness", 0.4) >= 0.6:
            trait_parts.append("爱开玩笑")
        if trait_parts:
            trait_hint = "。" + "，".join(trait_parts) + "。"
    except Exception as e:
        logger.warning(f"[关系] 读取性格特征失败: {e}")
        pass

    return f"【关系状态】好感:{affection:.0f} 信任:{trust:.0f}。{behavior}。语气{tone}。{emotion_hint}{trait_hint}"


def reset_relationship():
    """重置好感度/信任度为初始值（同时重置累积量、模式、冷却）"""
    now = datetime.now().isoformat()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE relationship SET value=?, updated_at=? WHERE key='affection'", (INITIAL_AFFECTION, now))
        cursor.execute("UPDATE relationship SET value=?, updated_at=? WHERE key='trust'", (INITIAL_TRUST, now))
        cursor.execute("UPDATE relationship SET value=?, updated_at=? WHERE key='recent_negative_count'", (0, now))
    invalidate_relationship_cache()
    # 重置每日累积量
    set_config("_rel_daily_affection", 0)
    set_config("_rel_daily_trust", 0)
    set_config("_rel_daily_date", "")
    set_config("_rel_mode_locked_until", "")
    # 删除预钳值（用 None 作为哨兵，避免 0 被误判为有效值）
    set_config("_rel_pre_clamp_affection", None)
    set_config("_rel_pre_clamp_trust", None)
    # 同时清空 AI 背景板
    set_config("ai_background", "")


def set_relationship_by_foundation(foundation_type: str):
    """根据基石类型设置初始好感和信任值"""
    from core.prompt_builder import get_foundation_defaults
    affection, trust = get_foundation_defaults(foundation_type)
    now = datetime.now().isoformat()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE relationship SET value=?, updated_at=? WHERE key='affection'", (affection, now))
        cursor.execute("UPDATE relationship SET value=?, updated_at=? WHERE key='trust'", (trust, now))
    invalidate_relationship_cache()
    logger.info(f"[关系] 根据基石类型 '{foundation_type}' 设置初始值: 好感={affection}, 信任={trust}")
