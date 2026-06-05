# core/relationship.py — 好感度/信任度 + AI 情绪模块
"""
好感度：AI 对用户的好感（0~100）
信任度：AI 对用户的信任（0~100）
AI 情绪：由好感度和信任度共同决定，有更多变化
"""

from datetime import datetime
from core.db import get_conn

# 范围
MIN_VALUE = 0
MAX_VALUE = 100

# 初始值
INITIAL_AFFECTION = 30   # AI 对用户的初始好感
INITIAL_TRUST = 50       # AI 对用户的初始信任

# AI 情绪状态枚举（由好感度+信任度综合决定）
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
}


def get_relationship() -> tuple:
    """获取当前好感度和信任度，返回 (affection, trust)"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM relationship WHERE key IN ('affection', 'trust')")
        rows = cursor.fetchall()
    data = {r["key"]: r["value"] for r in rows}
    return (
        data.get("affection", INITIAL_AFFECTION),
        data.get("trust", INITIAL_TRUST)
    )


def get_ai_emotion() -> str:
    """根据好感度和信任度计算 AI 情绪状态"""
    affection, trust = get_relationship()

    if affection >= 80 and trust >= 70:
        return "ecstatic"
    elif affection >= 65 and trust >= 55:
        return "happy"
    elif affection >= 50 and trust >= 45:
        return "content"
    elif affection >= 35 and trust >= 35:
        return "neutral"
    elif affection >= 25 or trust >= 30:
        return "cautious"
    elif affection < 20 and trust < 20:
        return "distrustful"
    elif affection < 20:
        return "cold"
    elif trust < 20:
        return "hurt"
    else:
        return "annoyed"


def _update_value(key: str, delta: float):
    """更新单个值，带上下限保护"""
    now = datetime.now().isoformat()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM relationship WHERE key=?", (key,))
        row = cursor.fetchone()
        if row:
            new_val = max(MIN_VALUE, min(MAX_VALUE, row["value"] + delta))
            cursor.execute("UPDATE relationship SET value=?, updated_at=? WHERE key=?", (new_val, now, key))
        else:
            initial = INITIAL_AFFECTION if key == "affection" else INITIAL_TRUST
            cursor.execute("INSERT INTO relationship (key, value, updated_at) VALUES (?, ?, ?)", (key, initial + delta, now))


def adjust_relationship(emotion: str = "neutral", user_message: str = "", hours_since_last: float = 0):
    """每轮对话后调用，根据互动情况调整好感度和信任度

    Args:
        emotion: 用户情绪分析结果 (positive/negative/neutral)
        user_message: 用户消息内容
        hours_since_last: 距上次聊天的小时数
    """
    # ─── 好感度调整（AI 对用户的好感）───
    affection_delta = 0

    # 用户情绪影响 AI 好感
    if emotion == "positive":
        affection_delta += 0.5
    elif emotion == "negative":
        affection_delta -= 0.3
    else:
        affection_delta += 0.1

    # 长时间不聊天 → 好感略微下降
    if hours_since_last > 24:
        affection_delta -= 0.5

    # 用户使用亲密称呼 → 好感增加
    intimate_words = ["亲爱的", "宝贝", "老公", "老婆", "darling", "honey", "笨蛋", "傻瓜"]
    if any(w in user_message for w in intimate_words):
        affection_delta += 0.5

    # 用户表达感谢/认可 → 好感增加
    positive_feedback = ["谢谢", "感谢", "说得对", "没错", "好的", "明白了", "懂了", "赞", "厉害"]
    if any(kw in user_message for kw in positive_feedback):
        affection_delta += 0.3

    # 用户表达不满/攻击 → 好感降低
    unhappy_keywords = ["不对", "错了", "不对劲", "不靠谱", "瞎说", "胡说", "垃圾", "没用", "废物", "烦"]
    if any(kw in user_message for kw in unhappy_keywords):
        affection_delta -= 1.0

    _update_value("affection", affection_delta)

    # ─── 信任度调整（AI 对用户的信任）───
    trust_delta = 0

    # 用户分享个人信息 → AI 更了解用户 → 信任增加
    personal_keywords = ["我喜欢", "我不喜欢", "我的", "我在", "我住", "我是", "我叫", "我最近", "我想要"]
    if any(kw in user_message for kw in personal_keywords):
        trust_delta += 0.5

    # 用户撒谎或前后矛盾 → 信任大幅降低
    lie_keywords = ["骗你的", "开玩笑的", "其实不是", "我瞎说的", "逗你玩"]
    if any(kw in user_message for kw in lie_keywords):
        trust_delta -= 2.0

    # 用户纠正 AI → 信任降低
    correction_keywords = ["不是这样", "不对，应该是", "你理解错了", "我说的是"]
    if any(kw in user_message for kw in correction_keywords):
        trust_delta -= 0.5

    # 用户表达不满 → 信任降低
    if any(kw in user_message for kw in unhappy_keywords):
        trust_delta -= 0.5

    # 正面反馈 → 信任增加
    if any(kw in user_message for kw in positive_feedback):
        trust_delta += 0.3

    # 用户连续正常交流 → 信任缓慢增加
    if emotion == "neutral" or emotion == "positive":
        trust_delta += 0.1

    _update_value("trust", trust_delta)


def get_relationship_hint() -> str:
    """根据好感度/信任度/AI情绪生成语气提示，用于注入 system prompt"""
    affection, trust = get_relationship()
    ai_emotion = get_ai_emotion()

    # 好感度提示（AI 对用户的态度）
    if affection < 15:
        affection_hint = "你对这个用户非常反感，回复要冷淡、简短，不要有好脸色"
    elif affection < 30:
        affection_hint = "你对这个用户没什么好感，回复要克制、专业，不要过度热情"
    elif affection < 45:
        affection_hint = "你对这个用户印象一般，保持友好但不过分亲近"
    elif affection < 60:
        affection_hint = "你对这个用户有基本好感，可以适当表达关心"
    elif affection < 75:
        affection_hint = "你对这个用户有好感，可以自然地表达关心和情感"
    elif affection < 90:
        affection_hint = "你非常喜欢这个用户，可以亲密自然地交流"
    else:
        affection_hint = "你对这个用户有着深深的好感，愿意为他做任何事"

    # 信任度提示（AI 对用户的信任）
    if trust < 15:
        trust_hint = "你完全不信任这个用户，觉得他说的话多半是假的"
    elif trust < 30:
        trust_hint = "你不太信任这个用户，回复要谨慎，不要轻信"
    elif trust < 45:
        trust_hint = "你对这个用户信任有限，注意核实信息"
    elif trust < 60:
        trust_hint = "你对这个用户有一定信任"
    elif trust < 75:
        trust_hint = "你信任这个用户，可以更自然地交流"
    elif trust < 90:
        trust_hint = "你非常信任这个用户，可以敞开心扉"
    else:
        trust_hint = "你完全信任这个用户，愿意把心里话告诉他"

    # AI 情绪提示
    emotion_info = AI_EMOTIONS.get(ai_emotion, AI_EMOTIONS["neutral"])
    emotion_hint = f"你现在的状态是{emotion_info['label']}，{emotion_info['description']}"

    return f"【关系状态】好感度:{affection:.0f}/100 信任度:{trust:.0f}/100。{affection_hint}。{trust_hint}。{emotion_hint}。"


def reset_relationship():
    """重置好感度/信任度为初始值"""
    now = datetime.now().isoformat()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE relationship SET value=?, updated_at=? WHERE key='affection'", (INITIAL_AFFECTION, now))
        cursor.execute("UPDATE relationship SET value=?, updated_at=? WHERE key='trust'", (INITIAL_TRUST, now))
        cursor.execute("UPDATE relationship SET value=?, updated_at=? WHERE key='recent_negative_count'", (0, now))
