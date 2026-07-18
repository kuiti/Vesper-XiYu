"""数据迁移 API —— 全量导出/导入备份，支持加密云端同步。"""
import logging

logger = logging.getLogger(__name__)

# 允许导入/导出的表名白名单
_TABLE_WHITELIST = frozenset({
    "user_profile", "ai_personality_traits",
    "emotion_daily", "proactive_flags", "proactive_response_log",
    "chat_history", "config", "memory",
    "presets", "tiered_summary",
    "death_archive", "entities", "knowledge_graph",
    "empathy_feedback", "demand_patterns",
    "sentence_index", "memory_importance", "memory_history",
    "user_activity_stats", "favorites", "ai_diary",
    "emotion_log", "lorebook", "user_personas",
    "characters_v2", "user_conclusions", "user_vocabulary",
    "shared_moments", "story_arcs",
})


def _validate_table_name(table: str) -> str:
    """白名单校验表名，不通过时抛出 ValueError"""
    if table not in _TABLE_WHITELIST:
        raise ValueError(f"不允许操作的表: {table}")
    return table


import json
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from core.db import (
    get_chat_conn,
    get_conn, get_memory, get_all_chat_messages,
    get_presets,
    get_last_summary, set_config, set_memory, save_preset,
    add_summary, reset_active_memory, reset_msg_counter, get_active_tiered_summaries, get_death_archive, get_msg_counter,
    add_tiered_summary
)

router = APIRouter(prefix="/migrate", tags=["migrate"])

EXPORT_VERSION = 2


def _get_counter_detail():
    """导出计数器全部字段（含 last_level*_at）"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count, last_level1_at, last_level2_at, last_level3_at FROM summary_msg_counter WHERE id = 1")
        row = cursor.fetchone()
    if row:
        return {"count": row["count"], "last_level1_at": row["last_level1_at"],
                "last_level2_at": row["last_level2_at"], "last_level3_at": row["last_level3_at"]}
    return {"count": 0, "last_level1_at": 0, "last_level2_at": 0, "last_level3_at": 0}


def _query_all(table: str) -> list:
    """通用查询：导出某张表的全部行（表名白名单校验）"""
    _validate_table_name(table)
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table}")
        return [dict(r) for r in cursor.fetchall()]


def _collect_per_char_data() -> dict:
    """收集所有角色库的 per-character 数据。"""
    result = {}
    try:
        from core.character_card import CharacterCard
        all_cids = {0}
        for card_info in CharacterCard.list_all():
            cid = card_info.get("id", 0) if isinstance(card_info, dict) else 0
            if cid:
                all_cids.add(cid)
        for cid in sorted(all_cids):
            try:
                char_data = {
                    "chat_history": get_all_chat_messages(character_id=cid),
                    "tiered_summaries": get_active_tiered_summaries(character_id=cid),
                    "memory": get_memory(character_id=cid),
                    "death_archive": get_death_archive(character_id=cid),
                }
                try:
                    from core.db.misc import get_diary_entries
                    char_data["diary"] = get_diary_entries(limit=100, character_id=cid)
                except Exception:
                    char_data["diary"] = []
                result[str(cid)] = char_data
            except Exception:
                pass
    except Exception:
        pass
    return result


def _collect_export_data() -> dict:
    """收集导出数据，返回纯 dict（供 cloud.py 内部调用）"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM config")
        _SENSITIVE = {"api_key", "amap_key", "pin_code", "passphrase"}
        config = {}
        for row in cursor.fetchall():
            if row["key"] in _SENSITIVE:
                continue
            val = row["value"]
            if row["key"] == "cloud_config" and isinstance(val, dict):
                val = {k: v for k, v in val.items() if k not in ("passphrase", "passphrase_salt", "passphrase_key")}
            config[row["key"]] = val

    return {
        "version": EXPORT_VERSION,
        "exported_at": datetime.now().isoformat(),
        "config": config,
        "memory": get_memory(),
        "chat_history": get_all_chat_messages(),
        "chat_history_per_char": _collect_per_char_data(),
        "presets": get_presets(),
        "last_summary": get_last_summary(),
        "tiered_summaries": get_active_tiered_summaries(),
        "death_archive": get_death_archive(),
        "msg_counter": get_msg_counter(),
        "msg_counter_detail": _get_counter_detail(),
        # 新增表
        "user_profile": _query_all("user_profile"),
        "ai_personality_traits": _query_all("ai_personality_traits"),
        "empathy_feedback": _query_all("empathy_feedback"),
        "emotion_log": _query_all("emotion_log"),
        "emotion_daily": _query_all("emotion_daily"),
        "favorites": _query_all("favorites"),
        "ai_diary": _query_all("ai_diary"),
        "demand_patterns": _query_all("demand_patterns"),
        "sentence_index": _query_all("sentence_index"),
        # 新增表（本轮改造）
        "entities": _query_all("entities"),
        "memory_history": _query_all("memory_history"),
        "knowledge_graph": _query_all("knowledge_graph"),
        "memory_importance": _query_all("memory_importance"),
        "relationship": _query_all("relationship"),
        "proactive_response_log": _query_all("proactive_response_log"),
        "user_activity_stats": _query_all("user_activity_stats"),
    }


@router.get("/export")
async def export_all(request: Request):
    """导出全部数据为一个 JSON 文件"""
    from core.auth import _get_token
    import hmac
    # 云端模式下需要认证
    if _get_token():
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer ") or not hmac.compare_digest(auth_header[7:], _get_token()):
            return {"status": "error", "message": "Unauthorized"}
    return JSONResponse(
        content=_collect_export_data(),
        headers={"Content-Disposition": "attachment; filename=vesper_backup.json"}
    )


@router.post("/import")
async def import_all(request: Request, file: UploadFile = File(...), bg: BackgroundTasks = None):
    """从 JSON 备份文件恢复全部数据（聊天记录、配置、记忆等）。"""
    from core.auth import _get_token

    # 云端模式下需要认证
    if _get_token():
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer ") or not hmac.compare_digest(auth_header[7:], _get_token()):
            return {"status": "error", "message": "Unauthorized"}
    # 阶段1：解析和验证
    try:
        raw = await file.read()
        if len(raw) > 50 * 1024 * 1024:
            return {"status": "error", "message": "文件过大（最大 50MB）"}
        data = json.loads(raw)
    except Exception as e:
        return {"status": "error", "message": f"文件格式无效: {e}"}

    if "version" not in data:
        return {"status": "error", "message": "无效的备份文件"}

    # 阶段2：恢复数据
    try:
        # 恢复 config（跳过敏感 key，避免覆盖当前环境的凭证）
        for key, value in data.get("config", {}).items():
            if key in ("api_key", "amap_key"):
                continue
            set_config(key, value)

        # 恢复 memory
        for key, value in data.get("memory", {}).items():
            set_memory(key, value)

        # 恢复聊天记录（同一事务：清空+插入，失败不丢数据）
        chat_msgs = data.get("chat_history", [])
        valid_msgs = []
        for msg in chat_msgs:
            role = msg.get("role")
            content = msg.get("content")
            if role and content:
                valid_msgs.append((role, content, msg.get("timestamp")))
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chat_history")
            cursor.execute("DELETE FROM chat_fts")
            cursor.execute("DELETE FROM tiered_summary")
            cursor.execute("DELETE FROM death_archive")
            for role, content, timestamp in valid_msgs:
                cursor.execute("INSERT INTO chat_history (role, content, timestamp) VALUES (?, ?, ?)",
                              (role, content, timestamp or datetime.now().isoformat()))
            reset_msg_counter()
            reset_active_memory()


        # 恢复 presets
        for name, preset_data in data.get("presets", {}).items():
            save_preset(name, preset_data)

        # 恢复旧版摘要（兼容 v1 备份）
        s = data.get("last_summary")
        if s:
            add_summary(s.get("start_time", ""), s.get("end_time", ""),
                        s.get("summary", ""), s.get("key_points", []))

        # 恢复三级摘要（v2+）
        if data.get("version", 1) >= 2:
            with get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM tiered_summary")
                cursor.execute("DELETE FROM death_archive")
                if data.get("death_archive"):
                    for da in data["death_archive"]:
                        cursor.execute(
                            "INSERT INTO death_archive (original_id, level, summary, key_points, importance, start_time, end_time, created_at, archived_at) VALUES (?,?,?,?,?,?,?,?,?)",
                            (da.get("original_id"), da["level"], da["summary"],
                             json.dumps(da.get("key_points", []), ensure_ascii=False),
                             da.get("importance", 0.5), da.get("start_time"), da.get("end_time"),
                             da.get("created_at"), da.get("archived_at", datetime.now().isoformat()))
                        )
                # 恢复消息计数器
                counter_detail = data.get("msg_counter_detail")
                if counter_detail:
                    cursor.execute(
                        "UPDATE summary_msg_counter SET count = ?, last_level1_at = ?, last_level2_at = ?, last_level3_at = ? WHERE id = 1",
                        (counter_detail["count"], counter_detail.get("last_level1_at", 0),
                         counter_detail.get("last_level2_at", 0), counter_detail.get("last_level3_at", 0))
                    )
                elif "msg_counter" in data:
                    cursor.execute("UPDATE summary_msg_counter SET count = ? WHERE id = 1", (data["msg_counter"],))

            for ts in data.get("tiered_summaries", []):
                add_tiered_summary(
                    ts["level"], ts["summary"], ts.get("key_points", []),
                    ts.get("importance", 0.5), ts["remaining_days"],
                    ts.get("start_time"), ts.get("end_time"),
                    ts.get("source_summary_ids")
                )

        # 恢复新增表（通用方式：从数据推断列名，逐表处理）
        _extra_tables = [
            "user_profile", "ai_personality_traits",
            "emotion_log", "emotion_daily", "favorites", "ai_diary",
            "demand_patterns", "empathy_feedback", "relationship", "proactive_flags",
            "user_activity_stats", "sentence_index",
            # 本轮新增
            "entities", "memory_history", "knowledge_graph", "memory_importance",
            "proactive_response_log",
        ]
        with get_conn() as conn:
            cursor = conn.cursor()
            for table_name in _extra_tables:
                rows = data.get(table_name, [])
                if not rows:
                    continue
                # 从第一行推断列名
                columns = list(rows[0].keys())
                # 检查表是否存在这些列
                try:
                    _validate_table_name(table_name)
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    actual_cols = {r[1] for r in cursor.fetchall()}
                    valid_cols = [c for c in columns if c in actual_cols]
                    if not valid_cols:
                        continue
                except Exception:
                    continue
                col_str = ", ".join(valid_cols)
                placeholders = ", ".join(["?"] * len(valid_cols))
                try:
                    cursor.execute(f"DELETE FROM {table_name}")
                    for row in rows:
                        try:
                            vals = [row.get(c) for c in valid_cols]
                            cursor.execute(f"INSERT INTO {table_name} ({col_str}) VALUES ({placeholders})", vals)
                        except Exception as e:
                            logger.info(f"[导入] {table_name} 跳过一行: {e}")
                except Exception as e:
                    logger.warning(f"[导入] {table_name} 失败: {e}")

    except Exception as e:
        logger.warning(f"[导入] 恢复数据异常: {e}")
        return {"status": "error", "message": f"导入过程中出错: {e}，部分数据可能未恢复"}

    # 通知前端需要重建向量库
    return {
        "status": "ok",
        "message": "数据已恢复，请手动重建向量索引",
        "restored": {
            "chat_messages": len(data.get("chat_history", [])),
            "presets": len(data.get("presets", {})),
            "memories": len(data.get("memory", {})),
            "tiered_summaries": len(data.get("tiered_summaries", [])),
            "death_archive": len(data.get("death_archive", [])),
            "user_profile": len(data.get("user_profile", [])),
            "ai_personality_traits": len(data.get("ai_personality_traits", [])),
            "emotion_log": len(data.get("emotion_log", [])),
            "ai_diary": len(data.get("ai_diary", [])),
            "sentence_index": len(data.get("sentence_index", [])),
        }
    }
