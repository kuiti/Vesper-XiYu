# core/diary_utils.py — 日记生成共享逻辑
"""抽取自 scheduler.py 和 api/memory.py 的重复日记生成代码。"""
from datetime import datetime
from core.db import get_conn
from core.llm_client import call_llm


def get_today_messages(limit: int = 30) -> tuple[int, list, dict | None]:
    """获取今日消息、消息数、昨日情绪。

    Returns:
        (msg_count, today_msgs, yesterday_mood_row)
    """
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now().replace(day=datetime.now().day - 1)).strftime("%Y-%m-%d")
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM chat_history WHERE timestamp >= ?", (today,))
        msg_count = cursor.fetchone()["cnt"]
        cursor.execute(
            "SELECT content, role FROM chat_history WHERE timestamp >= ? ORDER BY id ASC LIMIT ?",
            (today, limit),
        )
        today_msgs = cursor.fetchall()
        cursor.execute("SELECT mood FROM ai_diary WHERE date = ?", (yesterday,))
        yest_row = cursor.fetchone()
    return msg_count, today_msgs, yest_row


def detect_mood(text: str) -> str:
    """从文本中检测情绪（关键词匹配）。"""
    mood_map = {
        "开心": ["开心", "高兴", "哈哈", "😊", "快乐", "不错", "棒"],
        "疲惫": ["累", "困", "疲惫", "辛苦", "忙", "加班"],
        "难过": ["难过", "伤心", "哭", "失落", "郁闷"],
        "温暖": ["谢谢", "暖心", "好", "爱", "温暖", "幸福", "感动"],
        "焦虑": ["焦虑", "担心", "紧张", "怕", "不安", "着急"],
        "生气": ["生气", "烦", "讨厌", "火大", "气死"],
    }
    scores = {mood: sum(w in text for w in words) for mood, words in mood_map.items()}
    return max(scores, key=scores.get) if any(scores.values()) else "平静"


def build_diary_prompt(
    today: str,
    msg_count: int,
    today_msgs: list,
    ai_name: str,
    user_name: str,
    yesterday_mood: str | None = None,
) -> str:
    """构建日记生成 prompt。"""
    recent_text = "\n".join(
        f"{user_name if r['role'] == 'user' else ai_name}: {r['content'][:200]}"
        for r in today_msgs
    )
    yesterday_hint = f"昨天{yesterday_mood}的心情。" if yesterday_mood else ""
    return (
        f"今天是{today}，{ai_name}和{user_name}今天聊了{msg_count}条消息。"
        f"{yesterday_hint}"
        f"以下是今天的对话：\n{recent_text}\n\n"
        f"请以「{ai_name}」的第一人称视角写一篇日记（100-150字），包含：\n"
        f"1. 今天和{user_name}聊了什么\n"
        f"2. {user_name}今天的心情\n"
        f"3. {ai_name}自己的感受\n"
        f"语气温暖自然，不要用「今天」开头。"
    )


def generate_diary_content(prompt: str, temperature: float = 0.8, max_tokens: int = 500, timeout: int = 30) -> str | None:
    """调用 LLM 生成日记内容，返回文本或 None。"""
    result = call_llm(prompt=prompt, temperature=temperature, max_tokens=max_tokens, timeout=timeout)
    if result and len(str(result)) > 10:
        return str(result).strip()
    return None