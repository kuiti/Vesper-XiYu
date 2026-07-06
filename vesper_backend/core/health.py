"""系统自检模块：数据库健康、向量索引状态、记忆系统统计。"""
import os
import logging
from datetime import datetime
from core.retry import silent_exc

logger = logging.getLogger(__name__)


def _safe_size(path: str) -> int:
    """安全获取文件大小"""
    try:
        return os.path.getsize(path) if os.path.exists(path) else 0
    except Exception:
        return 0


def check_db_health() -> dict:
    """检查主数据库的健康状况"""
    from core.db import DB_FILE, get_conn

    result = {
        "db_file": DB_FILE,
        "size_bytes": _safe_size(DB_FILE),
        "size_mb": round(_safe_size(DB_FILE) / 1048576, 2),
        "tables": {},
        "errors": [],
    }

    table_queries = [
        ("chat_history", "SELECT COUNT(*) as cnt FROM chat_history"),
        ("user_profile", "SELECT COUNT(*) as cnt FROM user_profile"),
        ("facts", "SELECT COUNT(*) as cnt FROM facts"),
        ("memory_importance", "SELECT COUNT(*) as cnt FROM memory_importance"),
        ("tiered_summary", "SELECT COUNT(*) as cnt FROM tiered_summary"),
        ("episodes", "SELECT COUNT(*) as cnt FROM episodes"),
        ("memories", "SELECT COUNT(*) as cnt FROM memory"),
        ("sentence_index", "SELECT COUNT(*) as cnt FROM sentence_index"),
        ("config", "SELECT COUNT(*) as cnt FROM config"),
        ("characters_v2", "SELECT COUNT(*) as cnt FROM characters_v2"),
    ]

    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            for name, sql in table_queries:
                try:
                    cursor.execute(sql)
                    result["tables"][name] = cursor.fetchone()["cnt"]
                except Exception:
                    pass  # 表可能不存在
    except Exception as e:
        result["errors"].append(f"DB连接失败: {e}")

    return result


def check_vector_health() -> dict:
    """检查 ChromaDB 向量索引的健康状况"""
    result = {
        "model_ready": False,
        "collections": {},
        "errors": [],
    }

    try:
        from core.vector_store.model import is_model_ready, get_collection
        result["model_ready"] = is_model_ready()
        if not result["model_ready"]:
            return result

        for col_name in ("sentence_index", "memory_store", "knowledge_base"):
            try:
                col = get_collection(col_name)
                count = col.count()
                result["collections"][col_name] = count
            except Exception as e:
                result["collections"][col_name] = -1
                result["errors"].append(f"{col_name}: {e}")
    except Exception as e:
        result["errors"].append(f"向量模块加载失败: {e}")

    return result


def check_memory_stats() -> dict:
    """检查记忆系统的运行统计"""
    result = {
        "facts": {"total": 0, "by_category": {}, "high_confidence": 0, "avg_confidence": 0.0},
        "retrieval": {"total_ignored_count": 0, "high_ignored_count": 0, "avg_access_count": 0.0},
        "profile": {"total_entries": 0, "high_confidence_entries": 0},
        "errors": [],
    }

    try:
        from core.db import get_conn
        with get_conn() as conn:
            cursor = conn.cursor()

            # 事实统计
            cursor.execute("SELECT COUNT(*) as cnt, AVG(confidence) as avg_conf FROM facts")
            row = cursor.fetchone()
            result["facts"]["total"] = row["cnt"] or 0
            result["facts"]["avg_confidence"] = round(row["avg_conf"] or 0.0, 4)

            cursor.execute("SELECT COUNT(*) as cnt FROM facts WHERE confidence >= 0.8")
            result["facts"]["high_confidence"] = cursor.fetchone()["cnt"] or 0

            cursor.execute("SELECT category, COUNT(*) as cnt FROM facts GROUP BY category ORDER BY cnt DESC")
            result["facts"]["by_category"] = {r["category"]: r["cnt"] for r in cursor.fetchall()}

            # 检索统计：忽略计数
            cursor.execute("SELECT COALESCE(SUM(ignored_count), 0) as total, COUNT(*) as cnt FROM memory_importance WHERE ignored_count > 0")
            row = cursor.fetchone()
            result["retrieval"]["high_ignored_count"] = row["cnt"] or 0
            result["retrieval"]["total_ignored_count"] = row["total"] or 0

            # 被忽略最多的记忆（top 5）
            cursor.execute(
                "SELECT id, ignored_count, access_count FROM memory_importance ORDER BY ignored_count DESC LIMIT 5"
            )
            result["retrieval"]["top_ignored"] = [
                {"id": r["id"], "ignored_count": r["ignored_count"], "access_count": r["access_count"]}
                for r in cursor.fetchall()
            ]

            cursor.execute("SELECT AVG(access_count) as avg FROM memory_importance")
            row = cursor.fetchone()
            result["retrieval"]["avg_access_count"] = round(row["avg"] or 0.0, 2)

            # 画像统计
            cursor.execute("SELECT COUNT(*) as cnt FROM user_profile WHERE confidence >= 0.6")
            result["profile"]["high_confidence_entries"] = cursor.fetchone()["cnt"] or 0

            cursor.execute("SELECT COUNT(*) as cnt FROM user_profile")
            result["profile"]["total_entries"] = cursor.fetchone()["cnt"] or 0

    except Exception as e:
        result["errors"].append(f"记忆统计失败: {e}")

    return result


def run_diagnostics() -> dict:
    """运行所有诊断检查，聚合结果"""
    return {
        "timestamp": datetime.now().isoformat(),
        "db": check_db_health(),
        "vector": check_vector_health(),
        "memory": check_memory_stats(),
    }
