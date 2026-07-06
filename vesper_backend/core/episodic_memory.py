# core/episodic_memory.py — 情景记忆：记录每次对话会话的完整上下文快照
"""情景记忆（Episodic Memory）：记录"那天发生了什么"的完整场景。

功能：
- save_episode()：会话结束时保存情景快照
- recall_episode()：按话题/情感/时间检索情景
- get_recent_episodes()：获取最近 N 个情景
- get_episode_timeline()：按时间线组织情景
"""

import json
import logging
from datetime import datetime, timedelta
from core.db import get_conn, get_config, get_chat_conn

logger = logging.getLogger(__name__)


def _link_related_facts(user_msgs: list, max_facts: int = 3) -> list:
    """查找与用户消息相关的活跃原子事实，用词语重叠率匹配。"""
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT value FROM user_profile WHERE key LIKE '_fact_%' AND confidence >= 0.7 ORDER BY extracted_at DESC LIMIT 30"
            )
            rows = cursor.fetchall()
        if not rows:
            return []
        user_text = " ".join(m.get("content", "") for m in user_msgs if len(m.get("content", "")) > 5)
        if not user_text:
            return []

        # 用户消息分词
        user_words = _segment(user_text)
        if not user_words:
            return []

        matched = []
        for r in rows:
            try:
                d = json.loads(r["value"])
                if d.get("status") == "active" and d.get("importance", 0) >= 5:
                    text = d.get("text", "")
                    if not text:
                        continue
                    # 事实分词，计算词语重叠率
                    fact_words = _segment(text)
                    if not fact_words:
                        continue
                    overlap = len(user_words & fact_words)
                    union = len(user_words | fact_words)
                    if union > 0 and overlap / union >= 0.4:
                        matched.append(text)
                        if len(matched) >= max_facts:
                            break
            except Exception:
                pass
        return matched
    except Exception:
        return []


def _segment(text: str) -> set:
    """分词（优先 jieba，降级为 2-gram）。"""
    try:
        import jieba
        return {w for w in jieba.cut(text) if len(w.strip()) > 1}
    except ImportError:
        # 降级：2-gram
        return {text[i:i+2] for i in range(len(text) - 1)}


def save_episode(start_time: str, end_time: str, messages: list,
                 emotion_summary: str = "", topic_summary: str = "",
                 character_id: int = 0):
    """保存一次对话会话的情景快照，并关联相关原子事实。

    Args:
        start_time: 会话开始时间 ISO 格式
        end_time: 会话结束时间 ISO 格式
        messages: 会话期间的消息列表 [{"role": "user/assistant", "content": "..."}]
        emotion_summary: 情感摘要（如"整体积极，中间有一段低落"）
        topic_summary: 话题摘要（如"聊了工作压力、晚饭计划"）
        character_id: 角色 ID，用于多角色隔离 (默认 0 = 无角色)
    """
    if not messages or len(messages) < 3:
        return

    user_msgs = [m for m in messages if m.get("role") == "user"]
    ai_msgs = [m for m in messages if m.get("role") == "assistant"]

    # 提取关键事件（用户的重要陈述）
    key_events = _extract_key_events(user_msgs)

    # 关联相关原子事实（来源追溯）
    linked_facts = _link_related_facts(user_msgs)
    if linked_facts:
        key_events.extend([f"(事实) {f}" for f in linked_facts])

    # 计算重要性（基于消息数量、关键事件数、情感强度）
    importance = _calculate_episode_importance(messages, key_events)

    # 自动生成摘要（如果未提供）
    if not topic_summary:
        topic_summary = _auto_topic_summary(messages)

    if not emotion_summary:
        emotion_summary = _auto_emotion_summary(messages)

    try:
        from core.db import get_chat_conn
        conn = get_chat_conn(character_id)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO episodes
               (start_time, end_time, emotion_summary, topic_summary, key_events,
                user_message_count, ai_message_count, importance)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (start_time, end_time, emotion_summary, topic_summary,
             json.dumps(key_events, ensure_ascii=False),
             len(user_msgs), len(ai_msgs), importance)
        )
        conn.commit()
        logger.info(f"[情景] 保存: {topic_summary[:50]}... (重要性{importance:.2f}, {len(messages)}条)")
    except Exception as e:
        logger.warning(f"[情景] 保存失败: {e}")


def _escape_like(s: str) -> str:
    """转义 LIKE 通配符 % 和 _"""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def recall_episode(query: str, limit: int = 3, character_id: int = 0) -> list:
    """按关键词全文检索情景记忆（按角色隔离）。"""
    try:
        from core.db import get_chat_conn
        conn = get_chat_conn(character_id)
        safe_query = _escape_like(query)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, start_time, end_time, emotion_summary, topic_summary,
                      key_events, user_message_count, importance
               FROM episodes
               WHERE topic_summary LIKE ? ESCAPE '\\'
                  OR emotion_summary LIKE ? ESCAPE '\\'
                  OR key_events LIKE ? ESCAPE '\\'
               ORDER BY importance DESC, start_time DESC
               LIMIT ?""",
            (f"%{safe_query}%", f"%{safe_query}%", f"%{safe_query}%", limit)
        )
        rows = cursor.fetchall()
        results = []
        for r in rows:
            ke = r["key_events"]
            try:
                key_events = json.loads(ke) if ke else []
            except (json.JSONDecodeError, TypeError):
                key_events = []
            results.append({
                "id": r["id"],
                "start_time": r["start_time"],
                "end_time": r["end_time"],
                "topic_summary": r["topic_summary"],
                "emotion_summary": r["emotion_summary"],
                "key_events": key_events,
                "importance": r["importance"],
                "user_message_count": r["user_message_count"],
            })
        return results
    except Exception as e:
        logger.warning(f"[情景] 检索失败: {e}")
        return []


def get_recent_episodes(limit: int = 5, character_id: int = 0) -> list:
    """获取最近 N 个情景。"""
    try:
        from core.db import get_chat_conn
        conn = get_chat_conn(character_id)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, start_time, end_time, emotion_summary, topic_summary,
                      key_events, user_message_count, importance
               FROM episodes
               ORDER BY start_time DESC
               LIMIT ?""",
            (limit,)
        )
        rows = cursor.fetchall()
        results = []
        for r in rows:
            ke = r["key_events"]
            try:
                key_events = json.loads(ke) if ke else []
            except (json.JSONDecodeError, TypeError):
                key_events = []
            results.append({
                "id": r["id"],
                "start_time": r["start_time"],
                "end_time": r["end_time"],
                "topic_summary": r["topic_summary"],
                "emotion_summary": r["emotion_summary"],
                "key_events": key_events,
                "importance": r["importance"],
                "user_message_count": r["user_message_count"],
            })
        return results
    except Exception as e:
        logger.warning(f"[情景] 查询失败: {e}")
        return []


def get_episode_timeline(days: int = 7, character_id: int = 0) -> list:
    """按时间线组织最近 N 天的情景。

    Returns:
        [{"date": "2026-06-18", "episodes": [...], "total_messages": N}, ...]
    """
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    try:
        from core.db import get_chat_conn
        conn = get_chat_conn(character_id)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, start_time, end_time, emotion_summary, topic_summary,
                      key_events, user_message_count, importance
               FROM episodes
               WHERE start_time >= ?
               ORDER BY start_time""",
            (cutoff,)
        )
        rows = cursor.fetchall()
        # 按日期分组
        by_date = {}
        for r in rows:
            date = r["start_time"][:10] if r["start_time"] else "unknown"
            if date not in by_date:
                by_date[date] = {"date": date, "episodes": [], "total_messages": 0}
            ke = r["key_events"]
            try:
                key_events = json.loads(ke) if ke else []
            except (json.JSONDecodeError, TypeError):
                key_events = []
            by_date[date]["episodes"].append({
                "id": r["id"],
                "start_time": r["start_time"],
                "topic_summary": r["topic_summary"],
                "emotion_summary": r["emotion_summary"],
                "key_events": key_events,
                "importance": r["importance"],
            })
            by_date[date]["total_messages"] += r["user_message_count"]

        return sorted(by_date.values(), key=lambda x: x["date"], reverse=True)
    except Exception as e:
        logger.warning(f"[情景] 时间线查询失败: {e}")
        return []


def cleanup_old_episodes(retain_days: int = 30) -> int:
    """清理超过 retain_days 天的旧情景记录。返回清理条数。"""
    try:
        cutoff = (datetime.now() - timedelta(days=retain_days)).isoformat()
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM episodes WHERE start_time < ?", (cutoff,))
            return cursor.rowcount
    except Exception as e:
        logger.warning(f"[情景] 清理失败: {e}")
        return 0


def get_episode_context(query: str = "", limit: int = 3, character_id: int = 0) -> str:
    """生成情景记忆上下文文本，用于注入 prompt。

    Args:
        query: 用户当前消息（用于相关性检索）
        limit: 最多返回几个情景
    """
    if query:
        episodes = recall_episode(query, limit=limit, character_id=character_id)
    else:
        episodes = get_recent_episodes(limit=limit, character_id=character_id)

    if not episodes:
        return ""

    parts = ["【记忆中的情景】"]
    for ep in episodes:
        time_str = ep["start_time"][:16].replace("T", " ") if ep["start_time"] else "?"
        part = f"- {time_str}: {ep['topic_summary'] or '日常对话'}"
        if ep["emotion_summary"]:
            part += f" (情感: {ep['emotion_summary']})"
        if ep["key_events"]:
            # 分离普通关键事件和关联事实
            facts = [e for e in ep["key_events"] if e.startswith("(事实)")]
            events = [e for e in ep["key_events"] if not e.startswith("(事实)")]
            if events:
                part += f" [关键: {'; '.join(events[:3])}]"
            if facts:
                part += f" (关联事实: {'; '.join(f[:30] for f in facts[:2])})"
        parts.append(part)

    return "\n".join(parts)


# ─── 内部工具函数 ───

def _extract_key_events(user_msgs: list) -> list:
    """从用户消息中提取关键事件（简易规则版）。"""
    events = []
    keywords = ["决定", "计划", "准备", "开始", "完成", "成功", "失败",
                "开心", "难过", "生气", "害怕", "紧张", "兴奋",
                "考试", "面试", "生日", "旅行", "搬家", "辞职", "入职"]

    for msg in user_msgs:
        content = msg.get("content", "")
        if len(content) < 5:
            continue
        # 包含关键词的消息视为关键事件
        if any(kw in content for kw in keywords):
            # 截取前 80 字作为事件描述
            events.append(content[:80])
        # 限制最多 10 个关键事件
        if len(events) >= 10:
            break

    return events


def _calculate_episode_importance(messages: list, key_events: list) -> float:
    """计算情景重要性（0.0-1.0）。"""
    # 基础分：消息数量
    msg_score = min(1.0, len(messages) / 50)  # 50条消息=满分

    # 关键事件加分
    event_score = min(1.0, len(key_events) / 5)  # 5个事件=满分

    # 情感强度加分（包含强烈情感词的消息占比）
    emotion_words = ["开心", "难过", "生气", "害怕", "紧张", "兴奋",
                     "感动", "失望", "焦虑", "孤独", "幸福", "绝望"]
    emotion_count = sum(1 for m in messages
                       if any(w in m.get("content", "") for w in emotion_words))
    emotion_score = min(1.0, emotion_count / 5)

    # 加权平均
    importance = 0.3 * msg_score + 0.4 * event_score + 0.3 * emotion_score
    return round(max(0.1, min(1.0, importance)), 2)


def _auto_topic_summary(messages: list) -> str:
    """自动生成话题摘要（简易版：提取用户消息中的高频词）。"""
    try:
        import jieba
        from collections import Counter

        user_msgs = [m["content"] for m in messages if m.get("role") == "user"]
        if not user_msgs:
            return ""

        all_words = []
        for content in user_msgs:
            words = [w for w in jieba.cut(content) if len(w) > 1]
            all_words.extend(words)

        # 排除停用词
        stop_words = {"用户", "一个", "这个", "那个", "什么", "怎么", "可以",
                      "应该", "知道", "觉得", "感觉", "现在", "今天", "昨天",
                      "明天", "但是", "因为", "所以", "如果", "已经", "还是"}
        filtered = [w for w in all_words if w not in stop_words]

        if not filtered:
            return "日常对话"

        top_words = [w for w, _ in Counter(filtered).most_common(5)]
        return "聊了" + "、".join(top_words)
    except ImportError:
        return "日常对话"


def _auto_emotion_summary(messages: list) -> str:
    """自动生成情感摘要（简易版：统计情感词频）。"""
    positive = ["开心", "高兴", "快乐", "幸福", "兴奋", "感动", "满意", "喜欢"]
    negative = ["难过", "伤心", "生气", "愤怒", "害怕", "紧张", "焦虑", "失望", "孤独"]

    pos_count = 0
    neg_count = 0
    for m in messages:
        content = m.get("content", "")
        pos_count += sum(1 for w in positive if w in content)
        neg_count += sum(1 for w in negative if w in content)

    total = pos_count + neg_count
    if total == 0:
        return "平静"

    if pos_count > neg_count * 2:
        return "积极愉快"
    elif neg_count > pos_count * 2:
        return "有些低落"
    elif pos_count > neg_count:
        return "整体积极"
    elif neg_count > pos_count:
        return "略有负面"
    else:
        return "情绪平稳"


def save_milestone(event_type: str, description: str, importance: float = 0.9, character_id: int = 0):
    """保存里程碑事件（如用户第一次提到某事），以高重要性情景记录。"""
    now = datetime.now().isoformat()
    conn = get_chat_conn(character_id)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO episodes (start_time, end_time, topic_summary, key_events, importance, user_message_count, ai_message_count)
           VALUES (?, ?, ?, ?, ?, 1, 1)""",
        (now, now, description,
         json.dumps([f"[里程碑]{event_type}:{description}"], ensure_ascii=False), importance)
    )
    conn.commit()


def recall_milestone(event_type: str, character_id: int = 0) -> str | None:
    """按事件类型查找里程碑记录，返回话题摘要或 None。"""
    conn = get_chat_conn(character_id)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT topic_summary FROM episodes WHERE key_events LIKE ? ORDER BY importance DESC LIMIT 1",
        (f"%[里程碑]{event_type}:%",)
    )
    row = cursor.fetchone()
    if row:
        return row["topic_summary"]
    return None


def detect_chapter_boundary(messages: list) -> bool:
    """检测对话是否到达章节边界（用户使用话题切换词）。"""
    if len(messages) < 2:
        return False
    last = messages[-1].get("content", "") if messages else ""
    topic_shifters = ["对了", "话说", "说起来", "突然想到", "换个话题", "另外"]
    return any(s in last for s in topic_shifters)


def generate_chapter_title(episodes: list) -> str:
    """根据情景列表自动生成章节标题（日期+话题摘要）。"""
    if not episodes:
        return "新章节"
    topic = episodes[0].get("topic_summary", "")
    date = episodes[0].get("start_time", "")[:10]
    if topic:
        return f"{date} {topic[:20]}"
    return f"{date} 对话"


def generate_recall_report(days: int = 7, character_id: int = 0) -> str:
    """生成近 N 天的回忆报告，包含聊天次数、最重要话题和情感基调。"""
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    conn = get_chat_conn(character_id)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT topic_summary, emotion_summary, importance, start_time FROM episodes WHERE start_time >= ? ORDER BY start_time DESC",
        (cutoff,)
    )
    episodes = cursor.fetchall()

    if not episodes:
        return f"近{days}天没有聊天记录"

    total = len(episodes)
    top = max(episodes, key=lambda e: e["importance"] or 0)
    emotions = [e["emotion_summary"] for e in episodes if e["emotion_summary"]]

    report = f"📊 近{days}天聊天报告\n━━━━━━━━━━━━━\n"
    report += f"聊天次数：{total} 次\n"
    report += f"最重要的话题：「{top['topic_summary']}」\n"
    if emotions:
        report += f"情感基调：{' '.join(emotions[:5])}"
    return report


def get_conversation_continuation(character_id: int = 0) -> str | None:
    """根据上次对话的时间间隔生成跨对话续接提示（新对话开始时调用）。"""
    conn = get_chat_conn(character_id)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT topic_summary, end_time FROM episodes ORDER BY end_time DESC LIMIT 1"
    )
    row = cursor.fetchone()

    if not row or not row["end_time"]:
        return None

    try:
        last_time = datetime.fromisoformat(row["end_time"])
        hours_since = (datetime.now() - last_time).total_seconds() / 3600
    except (ValueError, TypeError):
        return None

    topic = row["topic_summary"] or ""

    if hours_since < 2:
        return f"【续接提示】上次你们聊了「{topic}」，可以自然续上。" if topic else None
    elif hours_since < 24:
        return f"【续接提示】上次你们聊了「{topic}」，简单问一句后续。" if topic else None
    elif hours_since < 72:
        return f"【续接提示】上次你们聊了「{topic}」，先问候再决定是否提起。" if topic else None
    return None

