from fastapi import APIRouter
from core.db import (
    get_active_tiered_summaries, get_all_active_keypoints,
    get_death_archive, get_msg_counter, get_config, set_config,
    get_messages_since_last_tiered_summary
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
    return {
        "active_count": len(summaries),
        "by_level": {
            str(l): len([s for s in summaries if s["level"] == l])
            for l in [1, 2, 3]
        },
        "msg_count": msg_count,
        "next_level1": (10 - (msg_count % 10)) % 10 or 10,
        "next_level2": (50 - (msg_count % 50)) % 50 or 50,
        "next_level3": (100 - (msg_count % 100)) % 100 or 100,
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
