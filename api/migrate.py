import json
import os
import shutil
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse
from core.db import (
    get_db_connection, get_config, get_memory, get_all_chat_messages,
    get_todos, get_notes, get_countdowns, get_reminders, get_presets,
    get_last_summary, set_config, set_memory, add_chat_message,
    add_todo, add_note, add_countdown, add_reminder, save_preset,
    add_summary, reset_active_memory, clear_chat_history, init_db
)

router = APIRouter(prefix="/migrate", tags=["migrate"])

EXPORT_VERSION = 1

@router.get("/export")
async def export_all():
    """导出全部数据为一个 JSON 文件"""
    config = {}
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM config")
    for row in cursor.fetchall():
        config[row["key"]] = row["value"]
    conn.close()

    export = {
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
        "last_summary": get_last_summary()
    }

    return JSONResponse(
        content=export,
        headers={"Content-Disposition": "attachment; filename=sakura_backup.json"}
    )

@router.post("/import")
async def import_all(file: UploadFile = File(...), bg: BackgroundTasks = None):
    """从导出的 JSON 文件恢复全部数据"""
    try:
        raw = await file.read()
        if len(raw) > 50 * 1024 * 1024:  # 50MB 上限
            return {"status": "error", "message": "文件过大（最大 50MB）"}
        data = json.loads(raw)
    except:
        return {"status": "error", "message": "文件格式无效"}

    if "version" not in data:
        return {"status": "error", "message": "无效的备份文件"}

    # 恢复 config
    for key, value in data.get("config", {}).items():
        set_config(key, value)

    # 恢复 memory
    for key, value in data.get("memory", {}).items():
        set_memory(key, value)

    # 恢复聊天记录（先清空）
    clear_chat_history()
    for msg in data.get("chat_history", []):
        add_chat_message(msg["role"], msg["content"], msg.get("timestamp"))

    # 恢复 todos
    conn = get_db_connection()
    conn.execute("DELETE FROM todos")
    conn.commit()
    conn.close()
    for t in data.get("todos", []):
        add_todo(t["task"])

    # 恢复 notes
    conn = get_db_connection()
    conn.execute("DELETE FROM notes")
    conn.commit()
    conn.close()
    for n in data.get("notes", []):
        add_note(n["title"], n["content"])

    # 恢复 countdowns
    conn = get_db_connection()
    conn.execute("DELETE FROM countdowns")
    conn.commit()
    conn.close()
    for c in data.get("countdowns", []):
        add_countdown(c["name"], c["target"])

    # 恢复 reminders
    conn = get_db_connection()
    conn.execute("DELETE FROM reminders")
    conn.commit()
    conn.close()
    for r in data.get("reminders", []):
        add_reminder(r["content"], r["target_time"], r.get("level", 4))

    # 恢复 presets
    for name, preset_data in data.get("presets", {}).items():
        save_preset(name, preset_data)

    # 恢复摘要
    s = data.get("last_summary")
    if s:
        add_summary(s.get("start_time", ""), s.get("end_time", ""),
                    s.get("summary", ""), s.get("key_points", []))

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
            "memories": len(data.get("memory", {}))
        }
    }
