# api/demand.py — 需求分层调试 API
from fastapi import APIRouter
from core.demand_analyzer import get_user_patterns

router = APIRouter(prefix="/demand", tags=["demand"])


@router.get("/patterns")
def list_patterns():
    """获取已学习的用户需求模式"""
    patterns = get_user_patterns(limit=20)
    return {"patterns": patterns}


@router.get("/stats")
def demand_stats():
    """需求层级分布统计"""
    from core.db import get_conn
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT demand_level, COUNT(*) as cnt FROM demand_patterns GROUP BY demand_level ORDER BY cnt DESC"
        )
        rows = cursor.fetchall()
        cursor.execute("SELECT COUNT(DISTINCT trigger_context) FROM demand_patterns WHERE frequency >= 3")
        learned = cursor.fetchone()[0]
    return {
        "distribution": [{"level": r["demand_level"], "count": r["cnt"]} for r in rows],
        "learned_patterns": learned
    }
