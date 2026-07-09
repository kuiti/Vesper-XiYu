"""长期目标追踪 API —— 目标的创建、状态更新、删除与统计（per-character）。"""
from fastapi import APIRouter, Query
from core.db import get_chat_conn

router = APIRouter(prefix="/goal", tags=["goal"])


@router.get("/list")
async def goal_list(status: str = Query("active", description="active/stale/done/abandoned/all"),
                    character_id: int = Query(0, description="角色 ID，默认 0")):
    """获取指定角色的目标列表"""
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        if status == "all":
            cursor.execute("SELECT * FROM goal_tracking ORDER BY last_mentioned DESC")
        else:
            cursor.execute("SELECT * FROM goal_tracking WHERE status=? ORDER BY last_mentioned DESC", (status,))
        rows = cursor.fetchall()
    return {"goals": [dict(r) for r in rows], "character_id": character_id}


@router.post("/{goal_id}/status")
async def goal_update_status(goal_id: int, data: dict,
                             character_id: int = Query(0, description="角色 ID，默认 0")):
    """更新目标状态（per-character）"""
    if data is None:
        data = {}
    new_status = data.get("status", "active")
    from core.goal_tracker import update_goal_status
    update_goal_status(goal_id, new_status, character_id=character_id)
    return {"ok": True, "id": goal_id, "status": new_status, "character_id": character_id}


@router.post("/create")
async def goal_create(data: dict,
                      character_id: int = Query(0, description="角色 ID，默认 0")):
    """创建新目标（per-character）"""
    title = (data or {}).get("title", "")
    if not title.strip():
        from fastapi import HTTPException
        raise HTTPException(400, "目标不能为空")
    with get_chat_conn(character_id) as conn:
        conn.cursor().execute(
            "INSERT INTO goal_tracking (goal_text, status, first_mentioned, last_mentioned) VALUES (?, 'active', datetime('now'), datetime('now'))",
            (title.strip(),)
        )
    return {"ok": True, "character_id": character_id}


@router.delete("/{goal_id}")
async def goal_delete(goal_id: int,
                      character_id: int = Query(0, description="角色 ID，默认 0")):
    """删除目标（per-character）"""
    with get_chat_conn(character_id) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM goal_tracking WHERE id=?", (goal_id,))
        if c.rowcount == 0:
            from fastapi import HTTPException
            raise HTTPException(404, "目标不存在")
    return {"ok": True, "character_id": character_id}


@router.get("/stats")
async def goal_stats(character_id: int = Query(0, description="角色 ID，默认 0")):
    """目标统计（per-character）"""
    from core.goal_tracker import get_goal_stats
    return get_goal_stats(character_id=character_id)
