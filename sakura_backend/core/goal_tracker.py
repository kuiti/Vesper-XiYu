# core/goal_tracker.py — 长期目标追踪引擎
"""
从 summary_engine 的 key_points 中识别用户的目标/计划/意图，
追踪状态变化，在合适时机触发主动跟进。
"""

import logging
from datetime import datetime
from core.db import get_conn

logger = logging.getLogger(__name__)


def _call_llm(prompt: str, max_tokens: int = 300, json_mode: bool = False):
    """轻量 LLM 调用封装（委托给 core.llm_client）"""
    from core.llm_client import call_llm
    return call_llm(prompt=prompt, temperature=0.2, max_tokens=max_tokens, timeout=15, json_mode=json_mode)


def ingest_keypoints(key_points: list):
    """接收 summary_engine 新产生的 key_points，识别目标/计划类并写入 goal_tracking"""
    if not key_points:
        return

    prompt = f"""判断以下从对话中提取的要点是否属于用户的"目标/计划/意图"（用户想做什么、打算做什么、想学什么、想改变什么）。

要点列表：
{chr(10).join(f'- {kp}' for kp in key_points)}

只输出 JSON：
{{"goals": [{{"text": "目标描述", "category": "learning/health/project/habit/career/other"}}]}}
不是目标/计划的要点不要包含。如果没有目标/计划，输出空数组。"""

    data = _call_llm(prompt, 300, json_mode=True)
    if not data or not isinstance(data, dict):
        return
    goals = data.get("goals", [])

    now = datetime.now().isoformat()
    with get_conn() as conn:
        cursor = conn.cursor()
        for g in goals:
            text = g.get("text", "").strip()
            category = g.get("category", "other")
            if not text:
                continue
            # 检查是否已存在
            cursor.execute(
                "SELECT id FROM goal_tracking WHERE goal_text=?",
                (text,)
            )
            existing = cursor.fetchone()
            if existing:
                cursor.execute(
                    "UPDATE goal_tracking SET last_mentioned=?, category=? WHERE id=?",
                    (now, category, existing["id"])
                )
            else:
                # 写入暂存区，等用户确认
                cursor.execute(
                    "INSERT OR IGNORE INTO pending_goals (goal_text, category, extracted_at, status) VALUES (?, ?, ?, 'pending')",
                    (text, category, now)
                )
        if goals:
            logger.info(f"[GoalTracker] 录入 {len(goals)} 个目标: {[g.get('text', '')[:30] for g in goals]}")


def get_pending_goals(limit: int = 3) -> list:
    """获取待确认的目标列表"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, goal_text, category FROM pending_goals WHERE status='pending' ORDER BY extracted_at DESC LIMIT ?", (limit,))
        return [{"id": r["id"], "goal_text": r["goal_text"], "category": r["category"]} for r in cursor.fetchall()]


def confirm_goal(pending_id: int) -> bool:
    """确认目标：从暂存移入正式跟踪"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT goal_text, category FROM pending_goals WHERE id=?", (pending_id,))
        row = cursor.fetchone()
        if not row:
            return False
        now = datetime.now().isoformat()
        cursor.execute("SELECT id FROM goal_tracking WHERE goal_text=?", (row["goal_text"],))
        if not cursor.fetchone():
            try:
                cursor.execute("INSERT INTO goal_tracking (goal_text, category, status, first_mentioned, last_mentioned) VALUES (?, ?, 'active', ?, ?)",
                              (row["goal_text"], row["category"], now, now))
            except Exception:
                pass  # UNIQUE 约束冲突（并发确认），静默跳过
        cursor.execute("UPDATE pending_goals SET status='confirmed' WHERE id=?", (pending_id,))
        return True


def reject_goal(pending_id: int) -> bool:
    """拒绝目标"""
    with get_conn() as conn:
        conn.cursor().execute("UPDATE pending_goals SET status='rejected' WHERE id=?", (pending_id,))
    return True


def get_stale_goals(days_threshold: int = 7, limit: int = 3) -> list:
    """查询状态为 active 且超过 days_threshold 天未提及的目标"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM goal_tracking WHERE status='active' AND last_mentioned < datetime('now', ?) ORDER BY first_mentioned ASC LIMIT ?",
            (f"-{days_threshold} days", limit)
        )
        return [dict(r) for r in cursor.fetchall()]


def update_goal_status(goal_id: int, status: str):
    """手动更新目标状态"""
    with get_conn() as conn:
        conn.cursor().execute(
            "UPDATE goal_tracking SET status=? WHERE id=?",
            (status, goal_id)
        )


def record_follow_up(goal_id: int):
    """记录一次主动跟进"""
    now = datetime.now().isoformat()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE goal_tracking SET last_followed_up=?, follow_up_count=follow_up_count+1 WHERE id=?",
            (now, goal_id)
        )


def check_goal_completion(user_message: str) -> list:
    """用 LLM 判断用户是否在对话中暗示完成了某个目标，返回完成的 goal ID 列表"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, goal_text FROM goal_tracking WHERE status='active'")
        active_goals = [dict(r) for r in cursor.fetchall()]
    if not active_goals:
        return []

    goals_text = "\n".join(f"- [{g['id']}] {g['goal_text']}" for g in active_goals)
    prompt = f"""判断用户消息是否暗示他/她已经完成或放弃了以下某个目标。

活跃目标：
{goals_text}

用户消息："{user_message}"

只输出 JSON：{{"completed": [id列表], "abandoned": [id列表]}}
如果没有任何目标被完成或放弃，输出空数组。"""

    data = _call_llm(prompt, 200, json_mode=True)
    if not data or not isinstance(data, dict):
        return []
    completed = data.get("completed", [])
    abandoned = data.get("abandoned", [])

    with get_conn() as conn:
        cursor = conn.cursor()
        for gid in completed:
            try:
                cursor.execute("UPDATE goal_tracking SET status='done' WHERE id=?", (int(gid),))
                logger.info(f"[GoalTracker] 目标 #{gid} 标记为完成")
            except (ValueError, TypeError):
                logger.warning(f"[GoalTracker] 无效目标 ID: {gid}")
        for gid in abandoned:
            try:
                cursor.execute("UPDATE goal_tracking SET status='abandoned' WHERE id=?", (int(gid),))
                logger.info(f"[GoalTracker] 目标 #{gid} 标记为放弃")
            except (ValueError, TypeError):
                logger.warning(f"[GoalTracker] 无效目标 ID: {gid}")

    return completed + abandoned


def get_goal_stats() -> dict:
    """目标统计"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status, COUNT(*) as cnt FROM goal_tracking GROUP BY status")
        rows = {r["status"]: r["cnt"] for r in cursor.fetchall()}
        cursor.execute("SELECT COUNT(*) FROM goal_tracking WHERE follow_up_count > 0")
        followed = cursor.fetchone()[0]
        # 动态计算 stale：active 且 7 天未提及
        cursor.execute(
            "SELECT COUNT(*) FROM goal_tracking WHERE status='active' AND last_mentioned < datetime('now', '-7 days')"
        )
        stale = cursor.fetchone()[0]
    return {
        "active": rows.get("active", 0),
        "stale": stale,
        "done": rows.get("done", 0),
        "abandoned": rows.get("abandoned", 0),
        "followed_up": followed
    }
