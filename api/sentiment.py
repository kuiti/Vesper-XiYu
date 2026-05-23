import json
from core.db import get_config

_sentiment_cache = {}
import threading as _threading  # noqa
_sentiment_lock = _threading.Lock()

# fallback 默认值
FALLBACK_RESULT = {
    "sentiment": "neutral",
    "target": "other",
    "intent": "statement",
    "relationship_impact": 0
}


def analyze_sentiment(text):
    """用 LLM 分析用户消息，返回结构化情绪+关系影响数据
    返回 dict: {sentiment, target, intent, relationship_impact}
    sentiment: positive/negative/neutral
    target: ai/self/situation/other — 情绪指向谁
    intent: gratitude/clarification/complaint/attack/sharing/joke/statement
    relationship_impact: -2.0 ~ +2.0，负数伤害关系，正数增进关系
    """
    if not text or len(text.strip()) < 2:
        return dict(FALLBACK_RESULT)

    import hashlib
    key = hashlib.sha256(text.strip().encode()).hexdigest()
    with _sentiment_lock:
        if key in _sentiment_cache:
            return _sentiment_cache[key].copy()

    api_key = get_config("api_key", "")
    if not api_key:
        return dict(FALLBACK_RESULT)

    prompt = f"""分析用户消息，输出JSON（只输出JSON，不要其他文字）：
{{"sentiment":"positive/negative/neutral","target":"ai/self/situation/other","intent":"gratitude/clarification/complaint/attack/sharing/joke/statement","relationship_impact":-2到2的数值}}

规则：
- target: 情绪/话语指向谁。ai=冲AI来的，self=说自己，situation=说处境/环境，other=其他
- intent: 用户的真实意图。gratitude=感谢认可，clarification=澄清纠正(友善的纠正是为了更好交流)，complaint=抱怨吐槽(不指向AI)，attack=攻击(指向AI)，sharing=分享个人信息，joke=开玩笑，statement=中性陈述
- relationship_impact: 这条消息对AI与用户关系的影响。-2=严重伤害，0=无影响，+2=很大增进
- 关键区分：clarification（"不对，应该是周五"）≠ attack（"你瞎说什么"）。前者是友善澄清不扣分，后者才扣分
- complaint 指向 situation（"工作好烦"）不要扣分，指向 ai 才扣

消息：{text[:250]}"""

    from core.llm_client import call_llm
    result = call_llm(prompt=prompt, temperature=0, max_tokens=120, timeout=10, json_mode=True)
    if result:
        try:
            impact = float(result.get("relationship_impact", 0))
        except (ValueError, TypeError):
            impact = 0.0
        validated = {
            "sentiment": result.get("sentiment", "neutral"),
            "target": result.get("target", "other"),
            "intent": result.get("intent", "statement"),
            "relationship_impact": max(-2.0, min(2.0, impact))
        }
        # 仅 LLM 成功返回时才缓存
        with _sentiment_lock:
            _sentiment_cache[key] = validated
            if len(_sentiment_cache) > 200:
                _sentiment_cache.pop(next(iter(_sentiment_cache)))
    else:
        validated = dict(FALLBACK_RESULT)
        # 回退结果不缓存，下次重试

    return validated
