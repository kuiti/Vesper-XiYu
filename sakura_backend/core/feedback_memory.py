"""反馈记忆：记录用户对 AI 行为的反馈，让 AI 能记住并调整自己的行为。

工作原理：
1. 用户通过 /feedback 命令或自然语言表达对 AI 行为的不满
2. save_behavior_feedback() 存入 feedback_memory 表
3. get_behavior_rules() 生成"行为规则"注入 prompt
4. AI 看到规则后调整自身行为

与画像记忆的区别：
- 画像记忆: 关于用户的事实（"用户喜欢咖啡"）
- 反馈记忆: 关于 AI 行为的规则（"用户不喜欢被纠正语法"）
"""

import json
import logging
from datetime import datetime
from core.db import get_conn, get_config, set_config

logger = logging.getLogger(__name__)

# 反馈分类标签
_CATEGORY_LABELS = {
    "length": "回复长度",
    "style": "说话风格",
    "topic": "话题偏好",
    "behavior": "行为习惯",
    "privacy": "隐私边界",
}


def save_behavior_feedback(content: str, category: str = "behavior", source: str = "feedback_command"):
    """保存用户对 AI 行为的反馈。

    Args:
        content: 反馈原文，如"不要写那么长"、"别总问问题"
        category: 分类（length/style/topic/behavior/privacy）
        source: 来源（feedback_command / message_analysis）
    """
    if not content or not content.strip():
        return
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO feedback_memory (content, category, source, created_at, active)
                   VALUES (?, ?, ?, ?, 1)""",
                (content.strip(), category, source, datetime.now().isoformat())
            )
        logger.info(f"[反馈] 保存: [{category}] {content[:50]}")
    except Exception as e:
        logger.warning(f"[反馈] 保存失败: {e}")


def get_behavior_rules(max_rules: int = 3) -> str:
    """获取活跃的行为规则，用于注入 prompt。

    优先级：最近反馈 > 旧反馈，同类合并。
    Returns:
        "【行为规则】\n- 用户不喜欢被纠正语法\n- 用户偏好短回复"
    """
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT content, category, created_at FROM feedback_memory
                   WHERE active = 1 ORDER BY created_at DESC LIMIT 10"""
            )
            rows = cursor.fetchall()
    except Exception:
        return ""

    if not rows:
        return ""

    # 同类合并：同类只保留最近的一条
    seen_categories = {}
    for r in rows:
        cat = r["category"]
        if cat not in seen_categories:
            seen_categories[cat] = r["content"]

    rules = list(seen_categories.values())[:max_rules]
    return "【行为规则】\n" + "\n".join(f"- {r}" for r in rules)


def get_behavior_rules_text(max_rules: int = 3) -> str:
    """供外部调用的接口，返回纯文本行为规则（空字符串=无规则）。"""
    return get_behavior_rules(max_rules)


def mark_inactive(content: str):
    """将指定内容的反馈标记为不活跃（用户撤销反馈或已解决）。"""
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE feedback_memory SET active = 0 WHERE content = ?", (content,))
    except Exception as e:
        logger.warning(f"[反馈] 标记失效失败: {e}")
