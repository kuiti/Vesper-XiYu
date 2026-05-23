from fastapi import APIRouter
from core.db import get_memory, set_memory, delete_memory
from pydantic import BaseModel
from typing import Dict

router = APIRouter(prefix="/memory", tags=["memory"])

class MemoryItem(BaseModel):
    key: str
    value: str

@router.get("/")
async def list_memory() -> Dict[str, str]:
    """获取所有手动记忆（过滤内部下划线开头的）"""
    all_mem = get_memory()
    # 只返回不以 _ 开头的（用户手动记忆）
    return {k: v for k, v in all_mem.items() if not k.startswith("_")}

@router.post("/")
async def add_memory(item: MemoryItem):
    set_memory(item.key, item.value)
    return {"status": "ok"}

@router.delete("/{key}")
async def remove_memory(key: str):
    delete_memory(key)
    return {"status": "ok"}

@router.get("/vault")
async def memory_vault():
    """记忆保险箱：AI 记住的关于用户的所有信息"""
    from core.db import get_conn, get_active_tiered_summaries, get_all_active_keypoints
    # 用户画像
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value, confidence FROM user_profile ORDER BY confidence DESC")
        profile = [{"key": r["key"], "value": r["value"], "confidence": r["confidence"]} for r in cursor.fetchall()]
    # 关键信息
    keypoints = get_all_active_keypoints()
    # 摘要
    summaries = [s["summary"] for s in (get_active_tiered_summaries() or [])]
    return {"profile": profile, "keypoints": keypoints, "summaries": summaries}

@router.delete("/vault/{vtype}")
async def delete_memory_item(vtype: str, key: str = ""):
    """删除特定类型的记忆（key 通过 query 参数传递，避免路径编码问题）"""
    from core.db import get_conn
    if vtype == "profile":
        if not key:
            return {"status": "error", "message": "key 不能为空"}
        with get_conn() as conn:
            conn.cursor().execute("DELETE FROM user_profile WHERE key=?", (key,))
    elif vtype == "summary":
        if not key or len(key.strip()) < 2:
            return {"status": "error", "message": "key 至少需要2个字符"}
        with get_conn() as conn:
            conn.cursor().execute("DELETE FROM tiered_summary WHERE summary LIKE ?", (f"%{key}%",))
    else:
        return {"status": "error", "message": f"未知的记忆类型: {vtype}"}
    return {"status": "ok"}

# ─── AI 日记 ───

@router.get("/diary")
async def get_diary(limit: int = 30):
    from core.db import get_diary_entries
    return get_diary_entries(limit)

@router.post("/diary/generate")
async def generate_diary():
    """手动触发 AI 日记生成"""
    import asyncio
    from core.db import get_conn, get_config, save_diary_entry
    from datetime import datetime
    from core.llm_client import call_llm

    today = datetime.now().strftime("%Y-%m-%d")
    ai_name = get_config("ai_name", "佐仓")

    # 收集今日数据
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM chat_history WHERE timestamp >= ?", (today,))
        msg_count = cursor.fetchone()["cnt"]
        cursor.execute("SELECT content, role FROM chat_history WHERE timestamp >= ? ORDER BY id DESC LIMIT 20", (today,))
        recent = cursor.fetchall()

    recent_text = "\n".join([f"{'用户' if r['role']=='user' else ai_name}: {r['content'][:100]}" for r in reversed(recent)])
    prompt = f"今天是{today}。{ai_name}和用户今天聊了{msg_count}条消息。以下是今天的一些对话片段：\n{recent_text}\n\n请以{ai_name}的第一人称视角写一篇简短的日记（100字以内），内容包括：今天和用户聊了什么、自己的感受、用户今天的心情。语气温暖自然。"

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: call_llm(prompt=prompt, temperature=0.8, max_tokens=200, timeout=15))
    if result:
        mood = "温暖" if "开心" in result or "高兴" in result else "平静"
        save_diary_entry(today, result, mood)
        return {"ok": True, "content": result, "date": today}
    return {"ok": False, "message": "生成失败"}

@router.get("/today-learning")
async def today_learning():
    """今天 AI 了解到的新信息"""
    from core.db import get_conn
    from datetime import datetime
    today = datetime.now().isoformat()[:10]
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM user_profile WHERE extracted_at >= ? ORDER BY extracted_at DESC LIMIT 10", (today,))
        new_profile = [{"key": r["key"], "value": r["value"]} for r in cursor.fetchall()]
        # 今天的关键信息从摘要中提取
        cursor.execute("SELECT summary, key_points FROM tiered_summary WHERE created_at >= ? ORDER BY id DESC LIMIT 3", (today,))
        new_summaries = [{"summary": r["summary"][:200], "key_points": r["key_points"]} for r in cursor.fetchall()]
    has_new = bool(new_profile or new_summaries)
    return {"has_new": has_new, "new_profile": new_profile, "new_summaries": new_summaries}