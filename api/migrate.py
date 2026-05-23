import json
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse
from core.db import (
    get_conn, get_config, get_memory, get_all_chat_messages,
    get_todos, get_notes, get_countdowns, get_reminders, get_presets,
    get_last_summary, set_config, set_memory, add_chat_message,
    add_todo, add_note, add_countdown, add_reminder, save_preset,
    add_summary, reset_active_memory, reset_msg_counter, clear_chat_history, init_db,
    get_active_tiered_summaries, get_death_archive, get_msg_counter,
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


def _collect_export_data() -> dict:
    """收集导出数据，返回纯 dict（供 cloud.py 内部调用）"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM config")
        config = {row["key"]: row["value"] for row in cursor.fetchall()}

    return {
        "version": EXPORT_VERSION,
        "exported_at": datetime.now().isoformat(),
        "config": config,
        "memory": get_memory(),
        "chat_history": get_all_chat_messages(),
        "todos": get_todos(),
        "notes": get_notes(),
        "countdowns": get_countdowns(),
        "reminders": get_reminders(),
        "presets": get_presets(),
        "last_summary": get_last_summary(),
        "tiered_summaries": get_active_tiered_summaries(),
        "death_archive": get_death_archive(),
        "msg_counter": get_msg_counter(),
        "msg_counter_detail": _get_counter_detail()
    }


@router.get("/export")
async def export_all():
    """导出全部数据为一个 JSON 文件"""
    return JSONResponse(
        content=_collect_export_data(),
        headers={"Content-Disposition": "attachment; filename=sakura_backup.json"}
    )


@router.post("/import")
async def import_all(file: UploadFile = File(...), bg: BackgroundTasks = None):
    """从导出的 JSON 文件恢复全部数据"""
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
        # 恢复 config
        for key, value in data.get("config", {}).items():
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

        # 恢复 todos、notes、countdowns、reminders（单连接）
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM todos")
            for t in data.get("todos", []):
                cursor.execute("INSERT INTO todos (task, done, created) VALUES (?, ?, ?)",
                               (t["task"], t.get("done", 0), t.get("created", datetime.now().isoformat())))

            cursor.execute("DELETE FROM notes")
            for n in data.get("notes", []):
                cursor.execute("INSERT INTO notes (title, content, created) VALUES (?, ?, ?)",
                               (n["title"], n["content"], n.get("created", datetime.now().isoformat())))

            cursor.execute("DELETE FROM countdowns")
            for c in data.get("countdowns", []):
                cursor.execute("INSERT INTO countdowns (name, target_date) VALUES (?, ?)",
                               (c["name"], c["target"]))

            cursor.execute("DELETE FROM reminders")
            for r in data.get("reminders", []):
                cursor.execute(
                    "INSERT INTO reminders (content, target_time, level, done, last_reminded) VALUES (?, ?, ?, ?, ?)",
                    (r["content"], r["target_time"], r.get("level", 4), r.get("done", 0), r.get("last_reminded"))
                )

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

    except Exception as e:
        print(f"[导入] 恢复数据异常: {e}")
        return {"status": "error", "message": f"导入过程中出错: {e}，部分数据可能未恢复"}

    # 通知前端需要重建向量库
    return {
        "status": "ok",
        "message": "数据已恢复，请手动重建向量索引",
        "restored": {
            "chat_messages": len(data.get("chat_history", [])),
            "todos": len(data.get("todos", [])),
            "notes": len(data.get("notes", [])),
            "countdowns": len(data.get("countdowns", [])),
            "reminders": len(data.get("reminders", [])),
            "presets": len(data.get("presets", {})),
            "memories": len(data.get("memory", {})),
            "tiered_summaries": len(data.get("tiered_summaries", [])),
            "death_archive": len(data.get("death_archive", []))
        }
    }
