# core/vector_store/utils.py — 工具函数：分句 + 重要性打分
import re


def split_sentences(text: str) -> list:
    """按句号/感叹号/问号/换行分句，过滤空句和短句"""
    parts = re.split(r'(?<=[。！？!?\n])', text)
    return [s.strip() for s in parts if s.strip() and len(s.strip()) >= 2]


# ─── 重要性打分 ───
_DATE_PATTERN = re.compile(r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?|\d{1,2}月\d{1,2}[日号]?|明天|后天|下周|下个月')
_EMOTION_WORDS = re.compile(r'开心|难过|生气|伤心|高兴|兴奋|紧张|焦虑|害怕|担心|感动|失望|孤独|无聊|累|烦')
_IMPORTANT_WORDS = re.compile(r'考试|面试|生日|结婚|毕业|手术|住院|搬家|入职|离职|升职|分手|表白|求婚|怀孕|生孩子')
_PERSON_PLACE = re.compile(r'爸爸|妈妈|爷爷|奶奶|哥哥|姐姐|弟弟|妹妹|老师|老板|同事|朋友|同学|男朋友|女朋友|老公|老婆')


def calculate_importance(text: str, role: str = "user") -> float:
    """计算句子重要性分数（1-10），纯规则不调用LLM"""
    score = 5.0
    # 包含日期/时间 → +2
    if _DATE_PATTERN.search(text):
        score += 2.0
    # 包含人名/地名 → +1
    if _PERSON_PLACE.search(text):
        score += 1.0
    # 包含情感词 → +1
    if _EMOTION_WORDS.search(text):
        score += 1.0
    # 包含重要事件词 → +3
    if _IMPORTANT_WORDS.search(text):
        score += 3.0
    # 句子长度 > 50 字 → +1
    if len(text) > 50:
        score += 1.0
    # 用户消息 → +1（比 AI 回复重要）
    if role == "user":
        score += 1.0
    return max(1.0, min(10.0, score))