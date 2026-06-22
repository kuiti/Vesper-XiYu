# core/memory_consolidation.py — 记忆巩固：主动将重要短期记忆转化为长期记忆
"""记忆巩固（Memory Consolidation）：模拟睡眠巩固机制。

每天凌晨自动执行：
1. 扫描近期对话中的高重要性内容
2. 将未被向量化的关键消息写入长期记忆
3. 清理低价值的短期记忆
4. 生成每日记忆报告

触发方式：由 scheduler 或 run_background_tasks 调用
"""

import json
import logging
from datetime import datetime, timedelta
from core.db import get_conn, get_config, set_config

logger = logging.getLogger(__name__)


def consolidate_memories() -> dict:
    """执行记忆巩固，返回巩固报告。

    Returns:
        {"consolidated": N, "cleaned": M, "report": "..."}
    """
    today = datetime.now().strftime("%Y-%m-%d")

    # 检查今天是否已巩固
    last_consolidation = get_config("_last_consolidation_date", "")
    if last_consolidation == today:
        return {"consolidated": 0, "cleaned": 0, "report": "今天已巩固"}

    try:
        # Step 1: 扫描近期高重要性消息
        consolidated = _consolidate_recent_important()

        # Step 2: 清理低价值短期记忆
        cleaned = _cleanup_low_value_memories()

        # Step 3: 生成报告
        report = f"巩固 {consolidated} 条重要记忆，清理 {cleaned} 条低价值记忆"

        # 记录巩固日志
        _log_consolidation(consolidated, cleaned, report)

        set_config("_last_consolidation_date", today)
        logger.info(f"[巩固] {report}")

        return {"consolidated": consolidated, "cleaned": cleaned, "report": report}

    except Exception as e:
        logger.warning(f"[巩固] 执行失败: {e}")
        return {"consolidated": 0, "cleaned": 0, "report": f"失败: {e}"}


def _consolidate_recent_important() -> int:
    """扫描最近 3 天的对话，将高重要性内容写入长期记忆。"""
    from core.vector_store import add_sentence_vectors, is_model_ready

    if not is_model_ready():
        return 0

    cutoff = (datetime.now() - timedelta(days=3)).isoformat()
    consolidated = 0

    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            # 获取最近 3 天的消息
            cursor.execute(
                """SELECT id, role, content, timestamp
                   FROM chat_history
                   WHERE timestamp >= ? AND role = 'user'
                   ORDER BY id DESC LIMIT 100""",
                (cutoff,)
            )
            rows = cursor.fetchall()

        if not rows:
            return 0

        # 检查哪些消息已被向量化（通过 sentence_index）
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT msg_id FROM sentence_index")
            existing_ids = {r["msg_id"] for r in cursor.fetchall()}

        # 筛选未向量化且重要的消息
        important_keywords = [
            "决定", "计划", "准备", "开始", "完成", "成功", "失败",
            "喜欢", "讨厌", "习惯", "偏好", "梦想", "目标",
            "生日", "纪念日", "考试", "面试", "入职", "辞职",
            "家人", "朋友", "恋人", "宠物",
        ]

        for row in rows:
            msg_id = row["id"]
            content = row["content"]

            # 跳过已向量化的
            if msg_id in existing_ids:
                continue

            # 跳过短消息
            if len(content) < 10:
                continue

            # 检查是否包含重要关键词
            is_important = any(kw in content for kw in important_keywords)
            if not is_important:
                continue

            # 写入向量
            try:
                add_sentence_vectors(msg_id, content, "user")
                consolidated += 1
            except Exception as e:
                logger.warning(f"[巩固] 向量化失败 msg_id={msg_id}: {e}")

            # 限制每次巩固数量
            if consolidated >= 20:
                break

    except Exception as e:
        logger.warning(f"[巩固] 扫描失败: {e}")

    return consolidated


def _cleanup_low_value_memories() -> int:
    """清理低价值的短期记忆（过期摘要、冗余句子索引）。"""
    cleaned = 0

    try:
        # 1. 归档过期摘要（已衰减到 0 的）
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO death_archive
                   (original_id, level, summary, key_points, importance,
                    start_time, end_time, created_at)
                   SELECT id, level, summary, key_points, importance,
                          start_time, end_time, created_at
                   FROM tiered_summary
                   WHERE remaining_days <= 0 AND is_active = 1"""
            )
            archived = cursor.rowcount
            cursor.execute(
                "UPDATE tiered_summary SET is_active = 0 WHERE remaining_days <= 0 AND is_active = 1"
            )
            cleaned += archived

        # 2. 清理冗余句子索引（同一 msg_id 的重复句子）
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """DELETE FROM sentence_index
                   WHERE sid NOT IN (
                       SELECT MIN(sid) FROM sentence_index GROUP BY msg_id, seq
                   )"""
            )
            deduped = cursor.rowcount
            cleaned += deduped

        # 3. 清理超过 30 天的低重要性记忆向量
        with get_conn() as conn:
            cursor = conn.cursor()
            cutoff = (datetime.now() - timedelta(days=30)).isoformat()
            cursor.execute(
                """DELETE FROM sentence_index
                   WHERE created_at < ? AND msg_id NOT IN (
                       SELECT id FROM chat_history WHERE role = 'user'
                       AND (content LIKE '%喜欢%' OR content LIKE '%讨厌%'
                       OR content LIKE '%习惯%' OR content LIKE '%生日%')
                   )""",
                (cutoff,)
            )
            old_cleaned = cursor.rowcount
            cleaned += old_cleaned

        # 4. 清理 30 天前的旧情景记录
        try:
            from core.episodic_memory import cleanup_old_episodes
            cleaned += cleanup_old_episodes(retain_days=30)
        except Exception:
            pass

    except Exception as e:
        logger.warning(f"[巩固] 清理失败: {e}")

    return cleaned


def _log_consolidation(consolidated: int, cleaned: int, report: str):
    """记录巩固日志。"""
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO consolidation_log
                   (consolidated_at, source_count, target_count, details)
                   VALUES (?, ?, ?, ?)""",
                (datetime.now().isoformat(), consolidated, cleaned, report)
            )
    except Exception as e:
        logger.warning(f"[巩固] 日志记录失败: {e}")


def get_consolidation_report(limit: int = 5) -> list:
    """获取最近的巩固报告。"""
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT consolidated_at, source_count, target_count, details
                   FROM consolidation_log
                   ORDER BY id DESC LIMIT ?""",
                (limit,)
            )
            return [dict(r) for r in cursor.fetchall()]
    except Exception as e:
        logger.warning(f"[巩固] 报告查询失败: {e}")
        return []
