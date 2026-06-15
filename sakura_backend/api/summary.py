from fastapi import APIRouter
from core.db import (
    get_active_tiered_summaries, get_all_active_keypoints,
    get_death_archive, get_msg_counter,
    get_messages_since_last_tiered_summary, get_last_trigger_at
)

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("/active")
async def get_active():
    summaries = get_active_tiered_summaries()
    keypoints = get_all_active_keypoints()
    return {
        "summaries": summaries,
        "keypoints": keypoints,
        "by_level": {
            str(l): [s for s in summaries if s["level"] == l]
            for l in [1, 2, 3]
        }
    }


@router.get("/status")
async def summary_status():
    summaries = get_active_tiered_summaries()
    msg_count = get_msg_counter()
    # 使用实际触发阈值计算下次触发剩余消息数
    thresholds = {1: 10, 2: 50, 3: 100}
    next_levels = {}
    for level, threshold in thresholds.items():
        last = get_last_trigger_at(level)
        remaining = threshold - (msg_count - last)
        next_levels[f"next_level{level}"] = max(1, remaining)
    return {
        "active_count": len(summaries),
        "by_level": {
            str(l): len([s for s in summaries if s["level"] == l])
            for l in [1, 2, 3]
        },
        "msg_count": msg_count,
        **next_levels,
    }


@router.get("/archive")
async def get_archive():
    return {"archived": get_death_archive()}


@router.post("/reset")
async def reset_memory():
    from core.db import get_conn
    with get_conn() as conn:
        cursor = conn.cursor()
        # 归档所有活跃摘要
        cursor.execute("""
            INSERT INTO death_archive (original_id, level, summary, key_points, importance, start_time, end_time, created_at)
            SELECT id, level, summary, key_points, importance, start_time, end_time, created_at
            FROM tiered_summary WHERE remaining_days > 0
        """)
        cursor.execute("DELETE FROM tiered_summary")
        cursor.execute("UPDATE summary_msg_counter SET count = 0, last_level1_at = 0, last_level2_at = 0, last_level3_at = 0 WHERE id = 1")
    return {"status": "ok"}
