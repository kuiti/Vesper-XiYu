import json
from collections import OrderedDict
from core.db import get_config

_sentiment_cache = OrderedDict()
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
    """用 LLM 分析用户消息，返回结构化情绪+关系影响数据
    返回 dict: {sentiment, target, intent, relationship_impact}
    sentiment: positive/negative/neutral
    target: ai/self/situation/other — 情绪指向谁
    intent: gratitude/clarification/complaint/attack/sharing/joke/playful/statement
    relationship_impact: -2.0 ~ +2.0，负数伤害关系，正数增进关系

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

    api_key = get_config("api_key", "")
    if not api_key:
        return dict(FALLBACK_RESULT)

    # 构建上下文（过滤天气卡片，减少到3条）
    context_text = ""
    if context:
        recent = [m for m in context[-5:] if not m.get("content", "").startswith("__WEATHER_CARD__")][-3:]
        lines = []
        for m in recent:
            role = "用户" if m.get("role") == "user" else "AI"
            content = m.get("content", "")[:60]
            lines.append(f"{role}：{content}")
        context_text = "最近对话：\n" + "\n".join(lines) + "\n\n"

    prompt = f"""分析用户消息的情感，结合对话上下文判断。输出JSON（只输出JSON）：
{{"sentiment":"positive/negative/neutral","target":"ai/self/situation/other","intent":"gratitude/clarification/complaint/attack/sharing/joke/playful/statement","emotion_subtype":"子类型","relationship_impact":-2到2的数值,"background_update":null}}

{context_text}用户最新消息：{text[:250]}

规则：
- target: 情绪指向谁。ai=冲AI来的，self=说自己，situation=说处境/环境，other=其他
- intent: 用户的真实意图。
  * gratitude=感谢认可
  * clarification=澄清纠正（"不对，应该是周五"）
  * complaint=抱怨AI（"你真烦""你怎么回事"）——指向AI才扣分
  * attack=攻击AI（"你瞎说什么""闭嘴"）——明确恶意才扣分
  * sharing=分享个人信息
  * joke=开玩笑（"我要吃了你""你完蛋了"）
  * playful=撒娇/调侃/耍赖（"哼""我不管""才不是""你猜""略略略""也行吧"）——不扣分
  * statement=中性陈述
- emotion_subtype: 细粒度情绪子类型（必须选一个）
  * negative类: tired=疲惫, frustrated=受挫/烦躁, sad=伤心/失落, anxious=焦虑/担心, lonely=孤独/想人, angry=生气/愤怒, wronged=委屈/不被理解, overwhelmed=压力大/撑不住
  * positive类: happy_share=分享开心, proud=自豪/成就感
  * playful类: teasing=撒娇/调侃
  * neutral类: neutral=中性
- relationship_impact: 对关系的影响。playful/joke/gratitude/sharing 是正向，complaint/attack 才负向
- background_update: 用户为AI设定背景时输出 {"action":"add/replace/remove","key":"类别","value":"内容"}，否则null
  key示例: nickname=用户外号, ai_nickname=AI外号, role=角色关系, preference=用户偏好, event=事件, personality=性格特点

**情绪子类型区分（中文口语）**：
- "好累""不想动了" → tired
- "又失败了""怎么这么烦" → frustrated
- "气死了""太过分了" → angry
- "没人懂我""凭什么" → wronged
- "好紧张""万一怎么办" → anxious
- "一个人好无聊" → lonely
- "太多了""要疯了" → overwhelmed

**关键区分（中文口语）**：
- "哼""切""才怪""才不是" → playful（撒娇），不是 complaint
- "我不管""你自己想""随便" → playful（耍赖），不是 attack
- "也行吧""嗯""哦" → statement（无所谓），不是 complaint
- "你完蛋了""我要打你" → joke（玩笑），不是 attack
- "讨厌""你好烦啊" → 要看上下文，可能是撒娇（playful）也可能是真抱怨（complaint）"""

    from core.llm_client import call_llm
    result = call_llm(prompt=prompt, temperature=0, max_tokens=250, timeout=10, json_mode=True)
    if result and isinstance(result, dict):
        try:
            impact = float(result.get("relationship_impact", 0))
        except (ValueError, TypeError):
            impact = 0.0
        bg = result.get("background_update")
        validated = {
            "sentiment": result.get("sentiment", "neutral"),
            "target": result.get("target", "other"),
            "intent": result.get("intent", "statement"),
            "emotion_subtype": result.get("emotion_subtype", "neutral"),
            "relationship_impact": max(-2.0, min(2.0, impact)),
            "background_update": bg if bg else None,
            "empathy_strategy": None,
            "context_keyword": detect_context_keyword(text)
        }
        # 仅 LLM 成功返回时才缓存
        with _sentiment_lock:
            if key in _sentiment_cache:
                _sentiment_cache.move_to_end(key)
            _sentiment_cache[key] = validated
            if len(_sentiment_cache) > 200:
                _sentiment_cache.popitem(last=False)  # LRU 驱逐
    else:
        validated = dict(FALLBACK_RESULT)
        # 回退结果不缓存，下次重试

    return validated
