"""
chat_tasks.py —— 从 chat.py 提取的后台任务和工具函数

包含：深度提示、DSML清理、提醒规则、背景更新、每日演化、成就、惊喜、RAG 上下文构建等。
"""

import asyncio
import json
import random
import re
import os
import time
from datetime import datetime, timedelta

from core.db import (
    get_config, set_config, get_conn,
)
from core.vector_store import search_similar, search_knowledge_similar, is_model_ready
import logging
from core.retry import silent_exc
logger = logging.getLogger(__name__)


# ─── DSML 清理 ───

def _clean_dsml(text: str) -> str:
    """清理 DSML 工具调用文本，防止泄露到聊天记录"""
    text = re.sub(r'<\|\|DSML\|\|tool_calls>.*?</\|\|DSML\|\|tool_calls>', '', text, flags=re.DOTALL)
    text = re.sub(r'<\|\|DSML\|\|[^>]*>', '', text)
    text = re.sub(r'</\|\|DSML\|\|[^>]*>', '', text)
    return text.strip()


# ─── 背景更新 ───

def _apply_background_update(background_update):
    """将 LLM（情感分析）检测到的背景更新写入 ai_background（结构化JSON）"""
    if not background_update:
        return
    if isinstance(background_update, dict):
        action = background_update.get("action", "add")
        key = background_update.get("key", "")
        value = background_update.get("value", "")
        if not key:
            return
        current = get_config("ai_background", "")
        bg = {}
        if current:
            try:
                bg = json.loads(current)
            except json.JSONDecodeError:
                bg = {"legacy": current}
        if action == "remove":
            bg.pop(key, None)
        elif action == "replace":
            bg[key] = value
        else:
            if key in bg and bg[key] == value:
                return
            bg[key] = value
        set_config("ai_background", json.dumps(bg, ensure_ascii=False))
        return
    if isinstance(background_update, str):
        bg_text = background_update.strip()
        if not bg_text:
            return
        current = get_config("ai_background", "")
        if current:
            try:
                existing = json.loads(current)
            except json.JSONDecodeError:
                existing = {"legacy": current}
        else:
            existing = {}
        if bg_text not in str(existing):
            existing[f"text_{len(existing)}"] = bg_text
            set_config("ai_background", json.dumps(existing, ensure_ascii=False))


# ─── 每日情绪演化 ───

def _trigger_daily_evolution():
    """触发每日情绪演化处理"""
    try:
        from core.emotion_evolution import process_daily_evolution
        process_daily_evolution()
    except Exception as e:
        logger.warning(f"[情绪演化] 触发异常: {e}")


# ─── 连续天数 + 成就 ───

def _calc_consecutive_days(msg_count, ws, loop):
    """后台计算连续互动天数 + 触发成就检查"""
    try:
        cutoff = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        from core.db import get_chat_conn
        from core.character_card import CharacterCard
        _card = CharacterCard.get_active()
        _cid = _card._db_id if _card and hasattr(_card, '_db_id') else 0
        chat_conn = get_chat_conn(_cid)
        cur = chat_conn.execute(
            "SELECT DISTINCT substr(timestamp,1,10) as d FROM chat_history "
            "WHERE timestamp >= ? ORDER BY d DESC", (cutoff,)
        )
        dates = [r["d"] for r in cur.fetchall()]
        today = datetime.now().strftime("%Y-%m-%d")
        consec = 0
        expected = datetime.strptime(today, "%Y-%m-%d")
        for d in dates:
            d_parsed = datetime.strptime(d, "%Y-%m-%d")
            if d_parsed == expected:
                consec += 1
                expected -= timedelta(days=1)
            else:
                break
        _check_achievements(msg_count, consec, ws, loop)
    except Exception as e:
        logger.warning(f"[连续天数] 计算失败: {e}")


def _check_achievements(msg_count, consecutive_days, ws, loop):
    """检查并解锁成就徽章，通过 WebSocket 推送通知"""
    try:
        from core.db import check_achievements as _check_ach
        from core.relationship import get_relationship
        affection, trust = get_relationship()
        hour = datetime.now().hour
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(DISTINCT substr(timestamp,1,10)) as days FROM chat_history")
            total_days = cursor.fetchone()["days"] or 0
        unlocked = _check_ach(msg_count, consecutive_days, total_days, hour, affection, trust)
        if unlocked:
            for a in unlocked:
                try:
                    asyncio.run_coroutine_threadsafe(
                        ws.send_text(json.dumps({"type": "achievement", "data": a})), loop
                    )
                except Exception as e:
                    silent_exc("_check_achievements", e)
    except Exception as e:
        logger.warning(f"[成就] 检查失败: {e}")


# ─── 小惊喜 ───

def _maybe_surprise(ws, loop):
    """后台随机触发小惊喜"""
    try:
        from core.relationship import get_relationship
        affection, _ = get_relationship()
        hour = datetime.now().hour
        last_surprise = get_config("_last_surprise", "")
        today = datetime.now().strftime("%Y-%m-%d")
        if affection >= 30 and hour >= 18 and last_surprise != today and random.random() < 0.1:
            from core.llm_client import call_llm
            ai_name = get_config("ai_name", "夕语")
            _p = get_config('personality', {})
            _tone = _p.get('tone', '冷静') if isinstance(_p, dict) else '冷静'
            prompt = (f"你是「{ai_name}」，一个AI伙伴。请给用户分享一个小惊喜——"
                      f"可以是一首短诗、一个有趣的冷知识、或一句暖心的话。不超过50字，语气{_tone}。")
            result = call_llm(prompt=prompt, temperature=0.9, max_tokens=100, timeout=10)
            if result:
                set_config("_last_surprise", today)
                asyncio.run_coroutine_threadsafe(
                    ws.send_text(json.dumps({"type": "surprise", "content": result})), loop
                )
    except Exception as e:
        logger.warning(f"[惊喜] 生成失败: {e}")


# ─── 目标完成检查 ───

def _check_goal_completion(user_message: str):
    """检查用户消息是否触发目标完成"""
    try:
        from core.goal_tracker import check_goal_completion
        check_goal_completion(user_message)
    except Exception as e:
        logger.warning(f"[目标检测] 异常: {e}")


def _run_demand_pattern_extraction():
    """后台：LLM 提炼用户需求模式（更新 demand_patterns.latent_need）"""
    try:
        from core.demand_analyzer import extract_patterns_via_llm
        extract_patterns_via_llm()
    except Exception as e:
        logger.warning(f"[需求模式] 提炼失败: {e}")


# ─── RAG 上下文构建（KB 标题匹配 + 向量搜索）───

def _build_rag_context(user_message: str, is_system: bool) -> tuple[str, str]:
    """构建 RAG 上下文：KB 标题提示 + 向量检索结果。

    Returns:
        (kb_title_hint, rag_context) — 两个字符串，为空表示无匹配。
    """
    kb_title_hint = ""
    if not is_system:
        try:
            now_ts = time.time()
            if not hasattr(_build_rag_context, '_kb_titles_cache') or now_ts - _build_rag_context._kb_titles_cache_ts > 60:
                from core.db import get_knowledge_filenames
                _build_rag_context._kb_titles_cache = get_knowledge_filenames()
                _build_rag_context._kb_titles_cache_ts = now_ts
            for title in _build_rag_context._kb_titles_cache:
                name = os.path.splitext(title)[0]
                if len(name) >= 2 and name in user_message:
                    kb_title_hint = f"【知识库关联】用户的话题可能与知识库文档「{title}」相关，你可以自然地引用其中的内容。"
                    break
        except Exception as e:
            silent_exc("_kb_title", e)

    rag_context = ""
    if not is_system and is_model_ready():
        try:
            similar_docs = search_similar(user_message, top_k=3, include_metadata=True)
            kb_docs = search_knowledge_similar(user_message, top_k=3)
            if similar_docs:
                RAG_THRESHOLD = 0.55
                rag_lines = []
                for doc, dist, meta in similar_docs:
                    cos_score = 1.0 - (dist / 2.0) if dist <= 2 else 0
                    if cos_score < RAG_THRESHOLD:
                        continue
                    if len(doc) > 300:
                        doc = doc[:300] + "..."
                    role = meta.get("role", "user") if meta else "user"
                    speaker = "你" if role == "assistant" else "用户"
                    rag_lines.append(f"{speaker}：{doc}")
                if rag_lines:
                    rag_context = "\n".join(rag_lines)
            if kb_docs:
                kb_lines = []
                for doc, dist in kb_docs:
                    cos_score = 1.0 - (dist / 2.0) if dist <= 2 else 0
                    if cos_score < RAG_THRESHOLD:
                        continue
                    if len(doc) > 300:
                        doc = doc[:300] + "..."
                    kb_lines.append(f"- {doc}")
                if kb_lines:
                    kb_context = "【知识库参考】\n" + "\n".join(kb_lines)
                    rag_context = (rag_context + "\n" + kb_context) if rag_context else kb_context
        except Exception as e:
            logger.warning(f"向量检索失败: {e}")

    return kb_title_hint, rag_context

# ─── 公开别名（供外部模块导入时使用完整函数名）───
clean_dsml = _clean_dsml
apply_background_update = _apply_background_update
build_rag_context = _build_rag_context
trigger_daily_evolution = _trigger_daily_evolution
calc_consecutive_days = _calc_consecutive_days
check_achievements = _check_achievements
maybe_surprise = _maybe_surprise
check_goal_completion = _check_goal_completion
