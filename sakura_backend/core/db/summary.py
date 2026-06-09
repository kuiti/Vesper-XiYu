# core/db/summary.py  |  tiered_summary + death_archive + summary_msg_counter

import json
from datetime import datetime
from . import get_conn
from .memory import get_memory, set_memory


# ========== conversation summary (旧版兼容) ==========
def get_last_summary():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM conversation_summary ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
    if row:
        return {
            "id": row["id"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "summary": row["summary"],
            "key_points": json.loads(row["key_points"]) if row["key_points"] else [],
            "created_at": row["created_at"]
        }
    return None


def add_summary(start_time, end_time, summary, key_points):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO conversation_summary (start_time, end_time, summary, key_points) VALUES (?, ?, ?, ?)",
            (start_time, end_time, summary, json.dumps(key_points, ensure_ascii=False))
        )
    set_memory("_active_summary", summary)
    old_keypoints = get_active_keypoints()
    merged = merge_keypoints(old_keypoints, key_points)
    set_memory("_active_keypoints", json.dumps(merged, ensure_ascii=False))


def get_active_summary():
    return get_memory().get("_active_summary", "")


def get_active_keypoints():
    val = get_memory().get("_active_keypoints", "[]")
    try:
        return json.loads(val)
    except (json.JSONDecodeError, ValueError):
        return []


def merge_keypoints(old_list, new_list, max_items=10):
    # 新关键点优先（new_list + old_list），最多保留 max_items 条，精确文本去重
    combined = new_list + old_list
    seen = set()
    unique = []
    for item in combined:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique[:max_items]


def reset_active_memory():
    set_memory("_active_summary", "")
    set_memory("_active_keypoints", "[]")


def get_messages_since_last_summary():
    last = get_last_summary()
    if last:
        start_time = last["end_time"]
    else:
        start_time = None
    with get_conn() as conn:
        cursor = conn.cursor()
        if start_time:
            cursor.execute("SELECT role, content, timestamp FROM chat_history WHERE timestamp > ? ORDER BY id", (start_time,))
        else:
            cursor.execute("SELECT role, content, timestamp FROM chat_history ORDER BY id")
        rows = cursor.fetchall()
    return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]


# ========== 三级摘要系统操作 ==========

# --- 消息计数器 ---
def get_msg_counter():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count FROM summary_msg_counter WHERE id = 1")
        row = cursor.fetchone()
    return row["count"] if row else 0


def increment_msg_counter():
    """原子递增并返回新值"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE summary_msg_counter SET count = count + 1 WHERE id = 1")
        cursor.execute("SELECT count FROM summary_msg_counter WHERE id = 1")
        row = cursor.fetchone()
    return row["count"] if row else 1


def decrement_msg_counter(amount: int = 2):
    """撤回消息时扣减计数器（默认扣2：一条用户+一条AI）"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE summary_msg_counter SET count = MAX(0, count - ?) WHERE id = 1", (amount,))


def get_last_trigger_at(level):
    if level not in (1, 2, 3):
        raise ValueError(f"Invalid level: {level}")
    col = f"last_level{level}_at"
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT {col} FROM summary_msg_counter WHERE id = 1")
        row = cursor.fetchone()
    return row[col] if row else 0


def set_last_trigger_at(level, count):
    if level not in (1, 2, 3):
        raise ValueError(f"Invalid level: {level}")
    col = f"last_level{level}_at"
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE summary_msg_counter SET {col} = ? WHERE id = 1", (count,))


def reset_msg_counter():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE summary_msg_counter SET count = 0, last_level1_at = 0, last_level2_at = 0, last_level3_at = 0 WHERE id = 1")


# --- 三级摘要 CRUD ---
def add_tiered_summary(level, summary, key_points, importance, remaining_days, start_time, end_time, source_ids=None):
    with get_conn() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute(
            """INSERT INTO tiered_summary
               (level, summary, key_points, importance, remaining_days, start_time, end_time, source_summary_ids, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (level, summary, json.dumps(key_points, ensure_ascii=False), importance, remaining_days,
             start_time, end_time, json.dumps(source_ids) if source_ids else None, now)
        )
        summary_id = cursor.lastrowid
    return summary_id


def get_active_tiered_summaries():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tiered_summary WHERE remaining_days > 0 ORDER BY level, created_at")
        rows = cursor.fetchall()
    result = []
    for r in rows:
        kp = r["key_points"]
        if isinstance(kp, str):
            try:
                kp = json.loads(kp)
            except (json.JSONDecodeError, ValueError):
                kp = []
        result.append({
            "id": r["id"], "level": r["level"], "summary": r["summary"],
            "key_points": kp or [], "importance": r["importance"],
            "remaining_days": r["remaining_days"], "start_time": r["start_time"],
            "end_time": r["end_time"], "created_at": r["created_at"],
            "mention_count": r["mention_count"] if "mention_count" in r.keys() else 0,
            "daily_boost": r["daily_boost"] if "daily_boost" in r.keys() else 0
        })
    return result


def get_tiered_summaries_by_level(level):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tiered_summary WHERE level = ? AND remaining_days > 0 ORDER BY created_at", (level,))
        rows = cursor.fetchall()
    result = []
    for r in rows:
        kp = r["key_points"]
        if isinstance(kp, str):
            try:
                kp = json.loads(kp)
            except (json.JSONDecodeError, ValueError):
                kp = []
        result.append({
            "id": r["id"], "level": r["level"], "summary": r["summary"],
            "key_points": kp or [], "importance": r["importance"],
            "remaining_days": r["remaining_days"],
            "mention_count": r["mention_count"] if "mention_count" in r.keys() else 0,
            "daily_boost": r["daily_boost"] if "daily_boost" in r.keys() else 0
        })
    return result


def get_all_active_keypoints(max_items=30):
    summaries = get_active_tiered_summaries()
    seen = set()
    unique = []
    for s in summaries:
        for kp in s.get("key_points", []):
            if kp not in seen:
                seen.add(kp)
                unique.append(kp)
    return unique[:max_items]


def get_messages_since_last_tiered_summary(limit=None):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT end_time FROM tiered_summary ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if row and row["end_time"]:
            sql = "SELECT role, content, timestamp FROM chat_history WHERE timestamp > ? ORDER BY id"
            params = (row["end_time"],)
        else:
            sql = "SELECT role, content, timestamp FROM chat_history ORDER BY id"
            params = ()
        if limit:
            # 先倒序取出最后 N 条再恢复顺序
            sql = sql.replace("ORDER BY id", "ORDER BY id DESC")
            sql += " LIMIT ?"
            params = (*params, limit) if params else (limit,)
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        if limit:
            rows = rows[::-1]  # 恢复时间正序
    return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]


def decay_summaries(days_elapsed):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE tiered_summary SET remaining_days = remaining_days - ? WHERE remaining_days > 0", (days_elapsed,))


def archive_expired_summaries():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tiered_summary WHERE remaining_days <= 0")
        expired = cursor.fetchall()
        count = 0
        for r in expired:
            cursor.execute(
                """INSERT INTO death_archive
                   (original_id, level, summary, key_points, importance, start_time, end_time, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (r["id"], r["level"], r["summary"], r["key_points"], r["importance"],
                 r["start_time"], r["end_time"], r["created_at"])
            )
            count += 1
        if expired:
            cursor.execute("DELETE FROM tiered_summary WHERE remaining_days <= 0")
    return count


def get_death_archive():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM death_archive ORDER BY archived_at DESC")
        rows = cursor.fetchall()
    return [{"id": r["id"], "original_id": r["original_id"], "level": r["level"],
             "summary": r["summary"], "key_points": json.loads(r["key_points"]) if r["key_points"] else [],
             "importance": r["importance"], "start_time": r["start_time"],
             "end_time": r["end_time"], "created_at": r["created_at"],
             "archived_at": r["archived_at"]} for r in rows]


# --- 提及计数 ---
def increment_mention(summary_id, boost_days):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE tiered_summary SET mention_count = mention_count + 1, daily_boost = daily_boost + ? WHERE id = ?",
            (boost_days, summary_id)
        )


def reset_daily_boost():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE tiered_summary SET daily_boost = 0 WHERE daily_boost > 0")


# --- 迁移 ---
def migrate_old_summaries():
    """一次性迁移，把 conversation_summary 导入 tiered_summary level=1"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM conversation_summary ORDER BY id")
        old_rows = cursor.fetchall()
        for r in old_rows:
            kp = r["key_points"]
            if isinstance(kp, str):
                try:
                    kp = json.loads(kp)
                except (json.JSONDecodeError, ValueError):
                    kp = []
            cursor.execute(
                """INSERT INTO tiered_summary
                   (level, summary, key_points, importance, remaining_days, start_time, end_time)
                   VALUES (1, ?, ?, 0.5, 5, ?, ?)""",
                (r["summary"], json.dumps(kp, ensure_ascii=False), r["start_time"], r["end_time"])
            )
        # 初始化消息计数为实际消息数
        cursor.execute("SELECT COUNT(*) FROM chat_history")
        msg_count = cursor.fetchone()[0]
        cursor.execute(
            "UPDATE summary_msg_counter SET count = ?, last_level1_at = ?, last_level2_at = ?, last_level3_at = ? WHERE id = 1",
            (msg_count, (msg_count // 10) * 10, (msg_count // 50) * 50, (msg_count // 100) * 100)
        )
    # 清空旧的活跃摘要缓存
    reset_active_memory()