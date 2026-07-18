# core/demand_analyzer.py — 需求模式存储 + 长期学习
"""
需求分层引擎的后端存储与学习模块。
- 每次对话的思考结果存入 demand_patterns 表
- get_user_patterns() 返回高频模式供 prompt_builder 注入
- extract_patterns_via_llm() 后台用 LLM 提炼用户行为规律
"""

import logging
from datetime import datetime
from core.db import get_chat_conn

logger = logging.getLogger(__name__)


def save_demand_record(demand: dict, user_message: str, character_id: int = 0):
    """保存一次需求分析记录到 demand_patterns 表"""
    if not demand or not user_message:
        return
    level = demand.get("level", "UNKNOWN")
    if level in ("LITERAL", "UNKNOWN"):
        return
    trigger = user_message.strip()[:100]
    now = datetime.now().isoformat()

    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        # check for existing record
        cursor.execute(
            "SELECT id, frequency FROM demand_patterns WHERE trigger_context=? AND demand_level=?",
            (trigger, level)
        )
        row = cursor.fetchone()
        if row:
            cursor.execute(
                "UPDATE demand_patterns SET frequency=?, last_matched=?, emotion_analysis=? WHERE id=?",
                (row["frequency"] + 1, now, demand.get("emotion", ""), row["id"])
            )
        else:
            cursor.execute(
                "INSERT INTO demand_patterns (trigger_context, demand_level, emotion_analysis, latent_need, frequency, last_matched, created_at) VALUES (?, ?, ?, ?, 1, ?, ?)",
                (trigger, level, demand.get("emotion", ""), demand.get("latent", ""), now, now)
            )


def get_user_patterns(limit: int = 10, character_id: int = 0) -> list:
    """获取高频需求模式（频率 >= 3），按频率降序（per-character）"""
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT trigger_context, demand_level, latent_need, frequency FROM demand_patterns WHERE frequency >= 3 ORDER BY frequency DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
    return [dict(r) for r in rows]


def extract_patterns_via_llm(character_id: int = 0):
    """后台任务：用 LLM 分析 demand_patterns 原始记录，提炼用户行为规律
    将提炼结果更新到 existing records 的 latent_need 字段（per-character）
    """
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, trigger_context, demand_level, emotion_analysis, frequency FROM demand_patterns WHERE frequency >= 3"
        )
        rows = cursor.fetchall()
    if not rows:
        return

    # 构建 prompt 给 LLM 分析
    records_text = "\n".join([
        f"- 触发词：「{r['trigger_context']}」 需求层级：{r['demand_level']} 情绪：{r.get('emotion_analysis','')} 频率：{r['frequency']}次"
        for r in rows
    ])

    prompt = f"""以下是用户与AI对话中的需求模式记录。请分析并提炼用户的行为规律：

{records_text}

请用JSON格式输出分析结果（只输出JSON，不要其他文字）：
{{"patterns": [
    {{"trigger_context": "触发词", "latent_need": "用户真正的深层需求（用中文描述，简洁）"}}
]}}

只提炼那些有明确规律的记录。如果没有明显规律，返回空数组。"""

    from core.llm_client import call_llm
    result = call_llm(prompt=prompt, temperature=0.3, max_tokens=800, timeout=30, json_mode=True)
    if not result or not isinstance(result, dict):
        return
    patterns = result.get("patterns", [])

    if not patterns:
        return

    # 更新 latent_need
    now = datetime.now().isoformat()
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        for p in patterns:
            trigger = p.get("trigger_context", "")
            latent = p.get("latent_need", "")
            if trigger and latent:
                cursor.execute(
                    "UPDATE demand_patterns SET latent_need=? WHERE trigger_context=?",
                    (latent, trigger)
                )
    logger.info(f"[需求模式提炼] 完成，更新了 {len(patterns)} 条模式")
