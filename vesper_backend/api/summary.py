"""摘要管理 API — 提供分层摘要查询、摘要状态、归档和重置等功能。"""
from fastapi import APIRouter, Request
from core.db import (
    get_active_tiered_summaries, get_all_active_keypoints,
    get_death_archive, get_msg_counter,
    get_messages_since_last_tiered_summary, get_last_trigger_at
)

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("/active")
async def get_active():
    """获取所有活跃的分层摘要和关键信息点。"""
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
    """获取摘要系统状态，包含各层级下次触发的剩余消息数。"""
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
    """获取已归档的历史摘要。"""
    return {"archived": get_death_archive()}


@router.post("/reset")
async def reset_memory(request: Request):
    """重置摘要系统：归档活跃摘要并清零计数器。"""
    from core.auth import _get_token
    import hmac
    # 云端模式下需要认证
    if _get_token():
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer ") or not hmac.compare_digest(auth_header[7:], _get_token()):
            return {"status": "error", "message": "Unauthorized"}
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
