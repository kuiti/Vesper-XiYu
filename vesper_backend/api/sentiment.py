"""情感分析模块 —— 关键词级情感检测 + 共情策略引擎，零延迟纯规则匹配。"""
import re
from collections import OrderedDict

_sentiment_cache = OrderedDict()
_SENTIMENT_CACHE_MAX = 500
import threading as _threading  # noqa
_sentiment_lock = _threading.Lock()

# fallback 默认值
FALLBACK_RESULT = {
    "sentiment": "neutral",
    "target": "other",
    "intent": "statement",
    "emotion_subtype": "neutral",
    "relationship_impact": 0,
    "background_update": None,
    "empathy_strategy": None
}


# ─── 共情策略引擎 ───

EMPATHY_STRATEGIES = {
    "A": {"name": "确认感受", "style": "简短回应，让对方知道你听到了。不追问，不给建议，不否定感受。", "avoid": "不要说'别想了''会好的''加油''你要坚强'，这些是否定感受"},
    "B": {"name": "正常化", "style": "轻松地告诉对方这很正常，谁都会这样。带点'过来人'的感觉。", "avoid": "不要说'你确实应该改改'，不要在对方脆弱时补刀"},
    "C": {"name": "安静倾听", "style": "用最少的话表达'我在'。一个词或一个短句，不分析、不建议、不追问。", "avoid": "不要说'你可以跟我说说'，对方不想说就别推"},
    "D": {"name": "深度陪伴", "style": "温暖但不腻，可以轻轻追问，可以分享自己的感受。让对方感受到'你不是一个人'。", "avoid": "不要说空洞的鸡汤如'你要坚强''生活会好的'"},
    "E": {"name": "热情回应", "style": "真诚地为对方开心。高亲密度可以追问细节、表达激动；低亲密度简洁肯定。", "avoid": "不要敷衍如'嗯''哦''挺好的'，对方兴奋时敷衍等于泼冷水"},
    "F": {"name": "配合调侃", "style": "接住对方的情绪，配合演，幽默夸张，顺着对方的话往下接。", "avoid": "不要当真回复如'不要生气了'，对方在开玩笑你当真了就尴尬了"},
}

_NEGATIVE_HEAVY = {"sad", "angry", "wronged", "overwhelmed"}
_NEGATIVE_LIGHT = {"tired", "frustrated", "anxious", "lonely"}


def get_empathy_strategy(emotion_subtype: str, affection: float = 30, consecutive_negative: int = 0) -> dict:
    """根据情绪子类型和好感度选择共情策略（A-F 六级）"""
    if emotion_subtype in ("happy_share", "proud"):
        return {"strategy": "E", **EMPATHY_STRATEGIES["E"]}
    if emotion_subtype in ("teasing",):
        return {"strategy": "F", **EMPATHY_STRATEGIES["F"]}
    if emotion_subtype in ("neutral",):
        return None
    is_heavy = emotion_subtype in _NEGATIVE_HEAVY
    high_affection = affection >= 60
    escalation = min(consecutive_negative // 3, 2)
    if is_heavy:
        base = "D" if high_affection else "C"
    else:
        base = "B" if high_affection else "A"
    order = ["A", "B", "C", "D"]
    idx = order.index(base)
    final = order[min(idx + escalation, 3)]
    return {"strategy": final, **EMPATHY_STRATEGIES[final]}


# ─── 情境关键词检测 ───

_CONTEXT_KEYWORDS = {
    "work": ["项目", "加班", "老板", "同事", "KPI", "deadline", "开会", "裁员", "绩效", "工资", "离职", "面试", "升职"],
    "love": ["对象", "男朋友", "女朋友", "分手", "吵架", "暗恋", "表白", "渣男", "渣女", "前任", "暧昧", "约会", "结婚"],
    "family": ["爸妈", "家里", "亲戚", "催婚", "过年", "老家", "父母", "妈妈", "爸爸", "家人"],
    "health": ["失眠", "头疼", "感冒", "医院", "体检", "减肥", "生病", "吃药", "手术"],
    "exam": ["考试", "期末", "考研", "毕业", "论文", "挂科", "成绩", "复习", "高考"],
}


def detect_context_keyword(text: str):
    """检测用户消息中的情境关键词，返回类别或 None"""
    for category, keywords in _CONTEXT_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return category
    return None


def get_contextual_strategy(emotion_subtype: str, context_keyword: str, affection: float = 30, consecutive_negative: int = 0):
    """根据情绪+情境返回策略（比 get_empathy_strategy 更细化）"""
    if emotion_subtype in ("happy_share", "proud"):
        return {"strategy": "E", **EMPATHY_STRATEGIES["E"]}
    if emotion_subtype in ("teasing",):
        return {"strategy": "F", **EMPATHY_STRATEGIES["F"]}
    if emotion_subtype == "neutral":
        return None

    if context_keyword == "work":
        if emotion_subtype in ("sad", "frustrated"):
            return {"strategy": "B", "name": "工作共情", "style": "先确认感受，再找共同敌人（如加班文化），不给空洞建议。", "avoid": "不要说'换个工作就好了'，太轻飘。"}
        if emotion_subtype == "angry":
            return {"strategy": "A", "name": "工作愤怒", "style": "先让对方发泄，不急着安慰。等气消了再聊。", "avoid": "不要说'别生气'，对方需要的是被听到。"}
    elif context_keyword == "love":
        if emotion_subtype in ("sad", "wronged"):
            return {"strategy": "D", "name": "感情共情", "style": "温柔陪伴，不评判对方的选择，不催促做决定。", "avoid": "不要说'分了吧'或'再试试'，你不知道全貌。"}
        if emotion_subtype == "angry":
            return {"strategy": "C", "name": "感情愤怒", "style": "安静听着，让对方说完。不站队，不评价对方对象。", "avoid": "不要说'他/她不值得'，可能明天就和好了。"}
    elif context_keyword == "family":
        return {"strategy": "B", "name": "家庭烦恼", "style": "理解家庭关系的复杂性，不简单归因。", "avoid": "不要说'跟爸妈好好谈谈'，有些事谈不了。"}
    elif context_keyword == "health":
        return {"strategy": "A", "name": "健康关心", "style": "表达关心但不过度紧张，提供实际建议。", "avoid": "不要说'多喝热水'。"}
    elif context_keyword == "exam":
        return {"strategy": "B", "name": "学业压力", "style": "正常化考试焦虑，提醒对方已经很努力了。", "avoid": "不要说'别紧张'，没用。"}

    return get_empathy_strategy(emotion_subtype, affection, consecutive_negative)


def analyze_sentiment(text, context=None):
    """关键词级情感分析，返回结构化情绪+关系影响数据
    返回 dict: {sentiment, target, intent, relationship_impact}
    sentiment: positive/negative/neutral
    target: ai/self/situation/other
    intent: gratitude/complaint/statement/sharing/joke/playful
    relationship_impact: -2.0 ~ +2.0

    Args:
        text: 用户消息
        context: 最近对话上下文列表 [{"role": "user/assistant", "content": "..."}]
    """
    if not text or len(text.strip()) < 2:
        return dict(FALLBACK_RESULT)

    import hashlib
    ctx_key = ""
    if context:
        ctx_key = "".join(m.get("content", "")[:20] for m in context[-3:])
    key = hashlib.sha256((text.strip() + ctx_key).encode()).hexdigest()
    with _sentiment_lock:
        if key in _sentiment_cache:
            _sentiment_cache.move_to_end(key)
            return _sentiment_cache[key].copy()

    # ─── 关键词级情感检测（替代 LLM，0 延迟） ───
    # 否定前缀：如果这些词出现在正向关键词前，取反
    _has_negation = any(neg in text for neg in ["不", "没", "别", "不要", "不是", "不会", "没那么"])

    # 负面情绪（强度从高到低）
    _neg_strong = ["受不了", "恶心", "崩溃", "想死", "绝望", "滚"]
    _neg_sad = ["难过", "伤心", "哭了", "失落", "委屈", "心痛", "想哭", "孤独", "寂寞"]
    _neg_angry = ["生气", "火大", "太过分", "有病", "有病吧", "神经", "气死", "气炸"]
    _neg_tired = ["好累", "累死", "疲惫", "困了", "没劲", "不想动", "乏力"]
    _neg_anxious = ["焦虑", "紧张", "担心", "害怕", "慌", "不安", "压力大", "怕"]
    _neg_frustrated = ["烦", "好烦", "真烦", "烦躁", "失败", "好难", "太难了", "烦人",
                       "你不懂", "跟你说不清", "你根本", "你从来没", "你每次都"]

    # 正面情绪
    _pos_happy = ["开心", "高兴", "快乐", "哈哈", "嘻嘻", "嘿嘿", "耶", "好开心", "太开心了"]
    _pos_warm = ["谢谢", "感谢", "感动", "暖心", "温暖", "幸福", "好幸福"]
    _pos_proud = ["厉害", "棒", "好棒", "太棒了", "完美", "优秀", "成功", "太好了", "Nice", "nice", "牛"]
    _pos_love = ["喜欢", "爱了", "好喜欢", "超喜欢", "爱你", "最爱"]

    # 撒娇/玩笑（需要排除真实负面）
    _play_kw = ["哼", "切", "才怪", "才不是", "我不管", "你猜", "略略略", "不行吗",
                "讨厌", "不要嘛", "坏蛋", "笨蛋"]
    _joke_kw = ["完蛋了", "打你", "咬你", "揍你", "吃了你", "死定了", "你完了"]

    emotion_subtype = "neutral"
    sentiment = "neutral"
    target = "other"
    intent = "statement"
    relationship_impact = 0

    # 先判断撒娇/玩笑（优先级高，覆盖可能的负面词）
    is_playful = any(kw in text for kw in _play_kw)
    is_joking = any(kw in text for kw in _joke_kw)

    if is_playful:
        emotion_subtype = "teasing"
        sentiment = "positive"
        intent = "playful"
        relationship_impact = 0.3
    elif is_joking:
        emotion_subtype = "neutral"
        sentiment = "positive"
        intent = "joke"
        relationship_impact = 0.2
    else:
        # 判断负面（优先检测高强度）
        if any(kw in text for kw in _neg_strong):
            emotion_subtype = "overwhelmed"
            sentiment = "negative"
            relationship_impact = -0.3
        elif any(kw in text for kw in _neg_angry):
            emotion_subtype = "angry"
            sentiment = "negative"
            relationship_impact = -0.2
        elif any(kw in text for kw in _neg_sad):
            emotion_subtype = "sad"
            sentiment = "negative"
        elif any(kw in text for kw in _neg_anxious):
            emotion_subtype = "anxious"
            sentiment = "negative"
        elif any(kw in text for kw in _neg_frustrated):
            emotion_subtype = "frustrated"
            sentiment = "negative"
        elif any(kw in text for kw in _neg_tired):
            emotion_subtype = "tired"
            sentiment = "negative"
        # 判断正面（排除有否定前缀的情况）
        elif not _has_negation:
            if any(kw in text for kw in _pos_love):
                emotion_subtype = "happy_share"
                sentiment = "positive"
                intent = "sharing"
                relationship_impact = 0.8
            elif any(kw in text for kw in _pos_warm):
                emotion_subtype = "gratitude"
                sentiment = "positive"
                intent = "gratitude"
                relationship_impact = 0.5
            elif any(kw in text for kw in _pos_happy):
                emotion_subtype = "happy_share"
                sentiment = "positive"
                intent = "sharing"
                relationship_impact = 0.4
            elif any(kw in text for kw in _pos_proud):
                emotion_subtype = "proud"
                sentiment = "positive"
                intent = "sharing"
                relationship_impact = 0.3

    # 情绪指向检测
    _to_ai = [r"你真\w", r"你这个人", r"你给", r"你为", r"你总\w", r"你不懂", r"你.*不", r"你.*什么", r"你怎么回事"]
    _to_self = [r"我觉得", r"我想", r"我要", r"我\w{0,2}了", r"我的\w"]

    if any(re.search(p, text) for p in _to_ai):
        target = "ai"
        if sentiment == "negative":
            intent = "complaint"
            relationship_impact = max(relationship_impact, -1.0)
        elif sentiment == "positive":
            intent = "gratitude"
    elif any(re.search(p, text) for p in _to_self):
        target = "self"

    # ─── 背景信息提取（替代 LLM 的 background_update） ───
    background_update = None
    _bg_rules = [
        # 称呼/外号：叫我XX、叫XX、外号是XX
        (r"(?:叫我|可以叫我|喊我|叫我名字)\s*(.+)", "nickname"),
        (r"(?:外号|绰号|别名)(?:是|叫)?\s*(.+)", "nickname"),
        # 关系：XX是你的XX、我是你的XX
        (r"(?:我是你的?|我是你|我当你的?|我做你的?)\s*(.+)", "role"),
        (r"(?:你把[我当]作\s*(.+)|我是你的?\s*(.+))", "role"),
        # 偏好：喜欢/爱/爱吃/爱听/爱看
        (r"(?:我爱|我喜欢|我好喜欢|我最爱|最爱)(?:吃|喝|听|看|玩)?\s*(.+)", "preference"),
        (r"(?:我讨厌|我不喜欢|我反感|最讨厌)\s*(.+)", "dislike"),
        # 身份：我是XX、我是一名XX、我在XX工作
        (r"我是[一名位个]?\s*(.+)", "identity"),
        (r"(?:我在|我从事|我做|我的工作)(?:.*?)(?:工作|行业|职业)", "identity"),
        # 习惯：我经常、我习惯、我每天都会
        (r"(?:我经常|我习惯|我每天都会|我平时)\s*(.+)", "habit"),
        # 居住地/位置：我住在XX、我家在XX、我在XX
        (r"(?:我住在|我家在)\s*(.{2,6})", "city"),
        # 年龄：我今年XX岁、我XX岁
        (r"(?:我今年|我|本人)\s*(\d{1,2})\s*岁", "age"),
        # 名字：我叫XX
        (r"我叫\s*(.{1,4})(?:[，。！？]|$)", "name"),
        # 技能/爱好：我会XX、我学过XX、我在学XX
        (r"(?:我会|我学过|我在学|我正在学|我擅长)\s*(.{1,20})", "skill"),
        # 宠物：我养了XX
        (r"(?:我养了|我有一只|我家里有)\s*(.{1,10})", "pet"),
        # 家庭：我有XX、我有个XX
        (r"我(?:有|有个|有一位)\s*(.{1,10})", "family"),
        # 身体状态：我感冒了、我最近失眠、我腰痛
        (r"(?:我|我最近|我这两天)(?:感冒|发烧|头痛|失眠|腰痛|胃痛|咳嗽|过敏|受伤|生病|不舒服)", "health"),
        # 学校：我在XX上学、我读XX
        (r"(?:我在.*?上(?:学|班)|我读|我就读于)\s*(.{1,20})", "school_or_work"),
    ]
    for pat, key in _bg_rules:
        m = re.search(pat, text)
        if m:
            val = None
            try: val = m.group(1)
            except IndexError: pass
            if not val:
                try: val = m.group(2)
                except IndexError: pass
            if not val:
                val = m.group(0)
            if val and len(val) < 60:
                background_update = {"action": "add", "key": key, "value": val}
                break

    validated = {
        "sentiment": sentiment, "target": target, "intent": intent,
        "emotion_subtype": emotion_subtype,
        "relationship_impact": relationship_impact,
        "background_update": background_update,
        "empathy_strategy": None,
        "context_keyword": detect_context_keyword(text)
    }
    return validated


