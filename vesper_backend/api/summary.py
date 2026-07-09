"""摘要管理 API — 提供分层摘要查询、摘要状态、归档和重置等功能。"""
from fastapi import APIRouter, Request, Query
from core.db import (
    get_active_tiered_summaries, get_all_active_keypoints,
    get_death_archive, get_msg_counter, get_chat_conn,
    get_messages_since_last_tiered_summary, get_last_trigger_at,
    reset_msg_counter,
)

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("/active")
async def get_active(character_id: int = Query(0, description="角色 ID，默认 0")):
    """获取指定角色的活跃分层摘要和关键信息点。"""
    summaries = get_active_tiered_summaries(character_id=character_id)
    keypoints = get_all_active_keypoints(character_id=character_id)
    return {
        "summaries": summaries,
        "keypoints": keypoints,
        "by_level": {
            str(l): [s for s in summaries if s["level"] == l]
            for l in [1, 2, 3]
        }
    }


@router.get("/status")
async def summary_status(character_id: int = Query(0, description="角色 ID，默认 0")):
    """获取指定角色的摘要系统状态，包含各层级下次触发的剩余消息数。"""
    summaries = get_active_tiered_summaries(character_id=character_id)
    msg_count = get_msg_counter(character_id=character_id)
    # 使用实际触发阈值计算下次触发剩余消息数
    thresholds = {1: 10, 2: 50, 3: 100}
    next_levels = {}
    for level, threshold in thresholds.items():
        last = get_last_trigger_at(level, character_id=character_id)
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
async def get_archive(character_id: int = Query(0, description="角色 ID，默认 0")):
    """获取指定角色的已归档历史摘要。"""
    return {"archived": get_death_archive(character_id=character_id)}


@router.post("/reset")
async def reset_memory(request: Request, character_id: int = Query(0, description="角色 ID，默认 0 重置所有角色")):
    """重置摘要系统：归档指定角色的活跃摘要并清零计数器。"""
    from core.auth import _get_token
    import hmac
    # 云端模式下需要认证
    if _get_token():
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer ") or not hmac.compare_digest(auth_header[7:], _get_token()):
            return {"status": "error", "message": "Unauthorized"}

    if character_id:
        # 重置单个角色
        conn = get_chat_conn(character_id)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO death_archive (original_id, level, summary, key_points, importance, start_time, end_time, created_at)
            SELECT id, level, summary, key_points, importance, start_time, end_time, created_at
            FROM tiered_summary WHERE remaining_days > 0
        """)
        cursor.execute("DELETE FROM tiered_summary")
        conn.commit()
        reset_msg_counter(character_id=character_id)
        return {"status": "ok", "character_id": character_id}
    else:
        # 重置所有角色 —— 遍历所有已知角色库
        from core.character_card import CharacterCard
        characters = CharacterCard.list_all()
        cids = {c.get("id") for c in characters}
        cids.add(0)  # 默认角色
        for cid in cids:
            conn = get_chat_conn(cid)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO death_archive (original_id, level, summary, key_points, importance, start_time, end_time, created_at)
                SELECT id, level, summary, key_points, importance, start_time, end_time, created_at
                FROM tiered_summary WHERE remaining_days > 0
            """)
            cursor.execute("DELETE FROM tiered_summary")
            conn.commit()
            reset_msg_counter(character_id=cid)
        return {"status": "ok", "character_ids": sorted(cids)}
