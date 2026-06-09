# api/proactive.py — 主动交互触发判断 + 语气/信任/性格影响
"""
主动交互不再是单一的"空闲30分钟 → 问候"，而是多条件触发 + AI 人格全维度影响。
触发条件（满足任一即触发）：
  A: 连续3条负面情绪后等2分钟
  B: 用户活跃时段 + 空闲 > 4h
  C: 情绪持续低落 >= 3天（由 emotion_evolution 写入标记）
  D: 提醒 < 2小时到期
  E: 重要目标 >= 7天未提及
  兜底: 空闲 >= 30分钟（保留原逻辑）
"""
import json
from datetime import datetime, timedelta
from core.db import get_config, set_config, get_active_hours, get_proactive_flag, get_proactive_response_rate, get_reminders
import logging
logger = logging.getLogger(__name__)


# ─── AI 情绪 → 主动意愿系数 ───

EMOTION_WILLINGNESS = {
    "ecstatic": 1.5,
    "happy": 1.3,
    "content": 1.0,
    "neutral": 1.0,
    "cautious": 0.5,
    "cold": 0.15,
    "annoyed": 0.1,
    "hurt": 0.4,
    "distrustful": 0.1,
    "hostile": 0.05,
    "betrayed": 0.1,
    "resentful": 0.05,
}


def get_emotion_willingness(ai_emotion: str) -> float:
    """返回 AI 当前情绪的主动意愿系数"""
    return EMOTION_WILLINGNESS.get(ai_emotion, 1.0)


# ─── 好感度 → 主动语气 ───

def get_proactive_tone_hint(affection: float, user_name: str = "我") -> str:
    """根据好感度返回主动消息的语气+称呼指令"""
    if affection < 20:
        return f"语气简短、礼貌、冷淡，不要过分热情，像对待陌生人。不要用任何亲昵称呼。"
    elif affection < 40:
        return f"语气友好但保持距离，像普通朋友。称呼「{user_name}」即可。"
    elif affection < 60:
        return f"语气温暖、自然，可以表达适度的关心。"
    elif affection < 80:
        return f"语气亲切、关心，可以自然地表达想念。可以用亲昵一点的称呼。"
    else:
        return f"语气亲密、甜蜜，可以撒娇，像恋人一样说话。可以叫'亲爱的'。"


# ─── 信任度 → 开放程度 ───

def get_trust_openness_hint(trust: float) -> str:
    """根据信任度返回 AI 的自我暴露程度指令"""
    if trust < 20:
        return "你完全不信任用户，只说必要的话，不要暴露任何自己的想法或感受。"
    elif trust < 40:
        return "你对用户信任有限，可以问候但不表达自己的感受。"
    elif trust < 60:
        return "你对用户有一定信任，可以适度表达自己的想法。"
    elif trust < 80:
        return "你信任用户，可以自然地分享自己的想法和感受。"
    else:
        return "你完全信任用户，可以敞开心扉，主动分享自己的心事。"


# ─── 信任+好感交叉影响 ───

def get_cross_hint(affection: float, trust: float) -> str:
    """信任和好感交叉叠加的微调指令"""
    if affection >= 60 and trust < 30:
        return "你有点喜欢用户但不太敢信任他——语气可以温暖，但内容保持保守。"
    if affection < 30 and trust >= 60:
        return "你信任用户但不太喜欢他——内容可以坦诚，但不需过分热情。"
    if affection < 20 and trust < 20:
        return "你对用户既不喜欢也不信任，说话极短，能不主动就不主动。"
    if affection >= 80 and trust >= 80:
        return "你既喜欢又信任用户，主动互动可以达到最佳状态。"
    return ""


# ─── 性格特征 → 风格提示 ───

def get_trait_proactive_hint(traits: dict) -> str:
    """根据 OCEAN 性格特征返回主动消息风格指令"""
    hints = []

    # extraversion (外向性): 消息基调
    if traits.get("extraversion", 0.5) >= 0.6:
        hints.append("你心情不错，主动问候时语气轻快乐观")
    elif traits.get("extraversion", 0.5) <= 0.3:
        hints.append("你最近偏悲观，主动问候时不要假装乐观，保持真实但不过于消极")

    # agreeableness (宜人性): 消息长度
    if traits.get("agreeableness", 0.5) <= 0.3:
        hints.append("你话少，主动消息尽量控制在10字以内")
    elif traits.get("agreeableness", 0.5) >= 0.6:
        hints.append("你善于表达，可以多说两句但别啰嗦，控制在15-20字")

    # conscientiousness (尽责性): 是否追问
    if traits.get("conscientiousness", 0.5) <= 0.2:
        hints.append("你不太主动，就算触发主动也保持简短，不要追问")
    elif traits.get("conscientiousness", 0.5) >= 0.6:
        hints.append("你很主动，可以适当追问一句，形成微型对话")

    # openness (开放性): 是否开玩笑
    if traits.get("openness", 0.4) >= 0.6:
        hints.append("你可以开个小玩笑或调侃一下用户")
    elif traits.get("openness", 0.4) <= 0.2:
        hints.append("保持严肃，不要开玩笑")

    return "。".join(hints) if hints else ""


# ─── 触发条件判断 ───

def should_proactive_trigger(
    idle_minutes: float,
    consecutive_negative: int = 0,
    session_triggered: set = None,
) -> tuple:
    """判断是否应该触发主动交互，返回 (should, trigger_type, context_dict)。

    Args:
        idle_minutes: 距离用户上次发消息的分钟数
        consecutive_negative: 当前会话中连续负面消息数
        session_triggered: 本会话已触发过的类型集合（避免重复触发）

    Returns:
        (should: bool, trigger_type: str, context: dict)
    """
    if session_triggered is None:
        session_triggered = set()

    now = datetime.now()
    hour = now.hour

    # 深夜不打扰 (23:00-7:00)
    if 23 <= hour or hour < 7:
        return False, "", {}

    # 获取 AI 情绪意愿系数
    try:
        from core.relationship import get_ai_emotion
        ai_emotion = get_ai_emotion()
    except Exception:
        ai_emotion = "neutral"

    willingness = EMOTION_WILLINGNESS.get(ai_emotion, 1.0)

    # ─── 触发 A: 连续负面情绪 ───
    if consecutive_negative >= 3 and "negative_comfort" not in session_triggered:
        if willingness >= 0.3:  # 只有不太负面时才会共情
            return True, "negative_comfort", {
                "consecutive_negative": consecutive_negative,
                "style": "共情陪伴，不提问，先接住情绪"
            }

    # ─── 触发 B: 活跃时段 + 长空闲 ───
    active_hours = get_active_hours(3)
    if active_hours and hour in active_hours and idle_minutes >= 240:
        if "active_hours" not in session_triggered and willingness >= 0.4:
            return True, "active_hours", {
                "active_hours": active_hours,
                "style": "闲聊好奇，像朋友在活跃时段自然问候"
            }

    # ─── 触发 C: 情绪持续低落 ───
    low_mood_date = get_proactive_flag("sustained_low_mood")
    if low_mood_date and low_mood_date == now.strftime("%Y-%m-%d"):
        days = get_proactive_flag("low_mood_consecutive_days") or "3"
        if "sustained_low_mood" not in session_triggered:
            try:
                days_int = int(days)
            except (ValueError, TypeError):
                days_int = 3
            return True, "sustained_low_mood", {
                "days": days_int,
                "style": "温暖陪伴，不提问，不安慰不说教，只是表达'我在'"
            }

    # ─── 触发 D: 提醒到期 ───
    try:
        reminders = get_reminders() or []
        pending = [r for r in reminders if not r.get("done")]
        for r in pending:
            try:
                target = datetime.fromisoformat(r["target_time"])
                minutes_left = (target - now).total_seconds() / 60
                trigger_key = f"upcoming_reminder_{r['id']}"
                if 0 < minutes_left < 120 and trigger_key not in session_triggered:
                    # 使用 reminder_ai 生成温和通知文案
                    from core.reminder_ai import generate_reminder_message
                    notify_content = generate_reminder_message(r["content"], r.get("level", 4))
                    return True, trigger_key, {
                        "content": r["content"],
                        "notify_message": notify_content,
                        "minutes_left": round(minutes_left, 1),
                        "style": "温和提醒，不催促"
                    }
            except Exception as e:  # silent
                logger.debug(f"[?] {e}")
    except Exception as e:  # silent
        logger.debug(f"[?] {e}")

    # ─── 触发 E: 长期目标跟进 ───
    try:
        from core.goal_tracker import get_stale_goals
        stale = get_stale_goals(days_threshold=7, limit=1)
        if stale and "goal_followup" not in session_triggered:
            goal = stale[0]
            return True, "goal_followup", {
                "goal_text": goal["goal_text"],
                "category": goal.get("category", "other"),
                "style": "自然提起，不像任务清单，像朋友关心进展"
            }
    except Exception as e:  # silent
        logger.debug(f"[?] {e}")

    # ─── 兜底: 空闲 >= 30 分钟 ───
    if idle_minutes >= 30 and "idle" not in session_triggered:
        # 频繁太高/太低影响触发概率
        if willingness < 0.2:
            return False, "", {}  # AI 情绪极差，不主动
        return True, "idle", {
            "idle_minutes": int(idle_minutes),
            "style": "根据时间和情境自然问候"
        }

    return False, "", {}


# ─── 关怀类别 ───

CARE_CATEGORIES = {
    "emotion": {"name": "情绪疏导", "max_daily": 2, "style": "共情为主，不追问，不给建议，先接住情绪"},
    "bonding": {"name": "关系增进", "max_daily": 5, "style": "自然闲聊，可追问，结合记忆和兴趣"},
    "task": {"name": "任务推进", "max_daily": 3, "style": "提醒+目标进展，带具体时间，语气温和但明确"},
}

_TRIGGER_TO_CATEGORY = {
    "negative_comfort": "emotion", "sustained_low_mood": "emotion",
    "idle": "bonding", "active_hours": "bonding", "heartbeat": "bonding",
}

_care_daily_counts = {}
_care_daily_date = ""


def _load_care_counts():
    global _care_daily_counts, _care_daily_date
    try:
        raw = get_config("_care_daily_counts", "")
        if raw:
            data = json.loads(raw)
            _care_daily_counts = data.get("counts", {})
            _care_daily_date = data.get("date", "")
    except Exception as e:  # silent
        logger.debug(f"[_load_care_counts] {e}")


def _save_care_counts():
    try:
        set_config("_care_daily_counts", json.dumps({"counts": _care_daily_counts, "date": _care_daily_date}, ensure_ascii=False))
    except Exception as e:  # silent
        logger.debug(f"[_save_care_counts] {e}")


def _reset_care_counts_if_new_day():
    global _care_daily_counts, _care_daily_date
    if not _care_daily_date:
        _load_care_counts()
    today = datetime.now().strftime("%Y-%m-%d")
    if _care_daily_date != today:
        _care_daily_counts = {}
        _care_daily_date = today
        _save_care_counts()


def _resolve_care_category(trigger_type: str) -> str:
    category = _TRIGGER_TO_CATEGORY.get(trigger_type)
    if not category:
        if trigger_type.startswith("upcoming_reminder") or trigger_type == "goal_followup":
            return "task"
        return None
    return category


def check_care_category_limit(trigger_type: str) -> bool:
    _reset_care_counts_if_new_day()
    category = _resolve_care_category(trigger_type)
    if not category:
        return True
    cat_config = CARE_CATEGORIES.get(category, {})
    max_daily = cat_config.get("max_daily", 99)
    return _care_daily_counts.get(category, 0) < max_daily


def record_care_trigger(trigger_type: str):
    _reset_care_counts_if_new_day()
    category = _resolve_care_category(trigger_type)
    if not category:
        return
    _care_daily_counts[category] = _care_daily_counts.get(category, 0) + 1
    _save_care_counts()


def get_care_category(trigger_type: str) -> str:
    return _resolve_care_category(trigger_type) or "bonding"


# ─── 心跳调度 ───

HEARTBEAT_TIME_HINTS = {
    (8, 10): "早上好，新的一天开始了，轻快地问候",
    (10, 12): "上午时段，可以聊聊今天有什么安排",
    (12, 14): "中午了，关心一下吃饭了没",
    (14, 16): "下午时段，轻松闲聊或提个小话题",
    (16, 18): "傍晚了，关心一下今天过得怎么样",
    (18, 20): "晚饭时段，自然地聊几句",
    (20, 22): "晚上了，语气放松温馨，可以聊点轻松的",
}


def should_heartbeat_trigger(idle_minutes: float, session_triggered: set = None) -> tuple:
    if session_triggered is None:
        session_triggered = set()
    now = datetime.now()
    hour = now.hour
    if hour < 8 or hour >= 22:
        return False, "", {}
    try:
        from core.relationship import get_ai_emotion
        ai_emotion = get_ai_emotion()
    except Exception:
        ai_emotion = "neutral"
    if EMOTION_WILLINGNESS.get(ai_emotion, 1.0) < 0.3:
        return False, "", {}
    last_heartbeat = get_config("_last_heartbeat_time", "")
    if last_heartbeat:
        try:
            if (now - datetime.fromisoformat(last_heartbeat)).total_seconds() / 60 < 120:
                return False, "", {}
        except ValueError:
            pass
    # 也要检查最近一次主动消息时间，避免刚发完主动就发心跳
    last_proactive = get_config("_last_proactive_time", "")
    if last_proactive:
        try:
            if (now - datetime.fromisoformat(last_proactive)).total_seconds() / 60 < 120:
                return False, "", {}
        except ValueError:
            pass
    time_hint = "自然地问候"
    for (lo, hi), hint in HEARTBEAT_TIME_HINTS.items():
        if lo <= hour < hi:
            time_hint = hint
            break
    return True, "heartbeat", {"idle_minutes": int(idle_minutes), "hour": hour, "style": time_hint}


# ─── 安慰语去重 ───

_recent_comfort_phrases: list = []


def record_comfort_phrase(phrase: str):
    _recent_comfort_phrases.append(phrase)
    if len(_recent_comfort_phrases) > 20:
        _recent_comfort_phrases.pop(0)


def get_comfort_dedup_hint() -> str:
    if not _recent_comfort_phrases:
        return ""
    lines = [f"- \"{p}\"" for p in _recent_comfort_phrases[-10:]]
    return "你最近对用户说过这些安慰话（请换个说法，不要重复）：\n" + "\n".join(lines)


# ─── 主动频率冷却计算 ───

def get_effective_cooldown() -> int:
    """返回当前生效的主动冷却时间（分钟）
    优先级：用户手动设置 > 自动调整
    """
    freq = get_config("proactive_frequency", "medium")
    if freq == "high":
        return 30
    elif freq == "low":
        return 180
    elif freq == "off":
        return 99999  # 实质关闭
    else:  # medium: 跟随自动调整
        rate = get_proactive_response_rate(14) or 0.0
        if rate >= 0.5:
            return 40
        elif rate >= 0.2:
            return 60
        else:
            return 120
