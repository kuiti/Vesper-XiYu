# core/conclusion_engine.py — 辩证用户建模
"""辩证用户建模：从对话中推理用户的行为模式、情感倾向和潜在需求，形成动态结论（per-character）。"""

import json
import logging
from datetime import datetime
from core.db import get_chat_conn, get_conn, get_config

logger = logging.getLogger(__name__)

_CONCLUSION_PROMPT = """基于以下对话和用户信息，推理出用户的行为模式、潜在需求、情感倾向。
只输出 JSON，不要解释不要多余内容：
{{"conclusions": [{{"text": "结论描述", "category": "behavior/preference/emotion/need", "confidence": 0.0-1.0}}]}}

要求：
- 不要重复已有结论（已有结论：{existing}）
- 关注变化和趋势，而非静态事实
- 每类最多输出2条
- 没有新的推理就输出空数组

用户画像：{profile}
最近对话：{episodes}"""


def run_conclusion_analysis(character_id: int = 0):
    """触发一次结论分析（per-character）。"""
    try:
        from core.llm_client import call_llm
        from core.episodic_memory import get_recent_episodes
        from core.profile_builder import get_profile_context

        # 获取已有结论（per-character）
        existing = get_active_conclusions(10, character_id=character_id)
        existing_text = "；".join([c["text"] for c in existing]) if existing else "无"

        # 获取用户画像（per-character）
        profile = get_profile_context(character_id=character_id) or "暂无"

        # 获取最近 episodes（per-character）
        episodes = get_recent_episodes(5, character_id=character_id)
        if not episodes:
            return
        episodes_text = "\n".join([
            f"[{e.get('start_time', '')[:10]}] {e.get('topic_summary', '')}"
            for e in episodes if e.get('topic_summary')
        ])
        if not episodes_text:
            return

        prompt = _CONCLUSION_PROMPT.format(
            existing=existing_text,
            profile=profile[:500],
            episodes=episodes_text[:1000],
        )

        result = call_llm(prompt=prompt, temperature=0.3, max_tokens=300, timeout=30, json_mode=True)
        if not result:
            return

        conclusions = []
        if isinstance(result, dict):
            conclusions = result.get("conclusions", [])
        elif isinstance(result, str):
            try:
                data = json.loads(result)
                conclusions = data.get("conclusions", [])
            except (json.JSONDecodeError, TypeError):
                return

        if not conclusions:
            return

        now = datetime.now().isoformat()
        saved = 0
        with get_chat_conn(character_id) as conn:
            cursor = conn.cursor()
            for c in conclusions:
                text = c.get("text", "").strip()
                category = c.get("category", "behavior")
                confidence = float(c.get("confidence", 0.7))
                if not text or confidence < 0.3:
                    continue
                # 检查是否与已有结论冲突
                cursor.execute(
                    "SELECT id FROM user_conclusions WHERE conclusion = ? AND status = 'active'",
                    (text,)
                )
                if cursor.fetchone():
                    continue
                cursor.execute(
                    "INSERT INTO user_conclusions (conclusion, category, confidence, evidence, source_episodes, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'active', ?, ?)",
                    (text, category, confidence, episodes_text[:200], json.dumps([e.get('topic_summary', '') for e in episodes[:3]], ensure_ascii=False), now, now)
                )
                saved += 1

        if saved:
            logger.info(f"[结论] 角色{character_id} 新增 {saved} 条用户结论")

    except Exception as e:
        logger.warning(f"[结论] 分析失败: {e}")


def get_active_conclusions(limit: int = 5, character_id: int = 0) -> list:
    """获取当前活跃的用户结论列表（per-character）。"""
    try:
        with get_chat_conn(character_id) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT conclusion, category, confidence FROM user_conclusions WHERE status = 'active' ORDER BY confidence DESC, updated_at DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
        return [{"text": r["conclusion"], "category": r["category"], "confidence": r["confidence"]} for r in rows]
    except Exception:
        return []


def get_conclusion_context(limit: int = 5, character_id: int = 0) -> str:
    """生成结论上下文字符串（仅含高置信度结论），用于注入 prompt。"""
    conclusions = get_active_conclusions(limit, character_id=character_id)
    if not conclusions:
        return ""
    parts = []
    for c in conclusions:
        if c["confidence"] >= 0.6:
            parts.append(c["text"])
    if not parts:
        return ""
    return "[Conclusions]" + "；".join(parts)
