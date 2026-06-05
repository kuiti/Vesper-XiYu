from fastapi import APIRouter
from core.db import get_memory, set_memory, delete_memory
from pydantic import BaseModel
from typing import Dict
import json as _json

_PROFILE_KEY_LABELS = {
    "user_student": "身份", "user_habit_stay_up": "习惯", "user_habit": "习惯",
    "name": "名字", "user_name": "称呼", "city": "城市", "gender": "性别", "age": "年龄",
    "occupation": "职业", "hobby": "爱好", "personality": "性格", "language": "语言",
}

def _human_label(key: str) -> str:
    if key in _PROFILE_KEY_LABELS:
        return _PROFILE_KEY_LABELS[key]
    return key.replace("user_", "").replace("_", " ")

def _human_value(val: str) -> str:
    if not val:
        return ""
    try:
        obj = _json.loads(val)
        if isinstance(obj, dict):
            return obj.get("text") or obj.get("value") or obj.get("name") or obj.get("summary") or str(obj)
    except (_json.JSONDecodeError, TypeError):
        pass
    return val

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
    import json
    # 用户画像（不含原子事实）
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value, confidence, extracted_at FROM user_profile WHERE key NOT LIKE '_fact_%' ORDER BY confidence DESC")
        profile = [{"key": _human_label(r["key"]), "raw_key": r["key"], "value": _human_value(r["value"]), "confidence": r["confidence"], "extracted_at": r["extracted_at"]} for r in cursor.fetchall()]
    # 原子事实
    facts = []
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value, confidence, extracted_at FROM user_profile WHERE key LIKE '_fact_%' ORDER BY extracted_at DESC")
        for r in cursor.fetchall():
            try:
                d = json.loads(r["value"])
                facts.append({
                    "key": r["key"],
                    "text": d.get("text", ""),
                    "category": d.get("category", ""),
                    "importance": d.get("importance", 5),
                    "confidence": r["confidence"],
                    "extracted_at": r["extracted_at"],
                })
            except Exception:
                pass
    # 实体
    entities = []
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT entity_text, entity_type, linked_memories, created_at FROM entities ORDER BY created_at DESC LIMIT 50")
        for r in cursor.fetchall():
            try:
                linked = json.loads(r["linked_memories"]) if r["linked_memories"] else []
            except Exception:
                linked = []
            entities.append({
                "text": r["entity_text"],
                "type": r["entity_type"],
                "linked_count": len(linked),
                "created_at": r["created_at"],
            })
    # 知识图谱
    knowledge = []
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT subject, predicate, object, confidence FROM knowledge_graph ORDER BY confidence DESC LIMIT 30")
        for r in cursor.fetchall():
            knowledge.append({
                "subject": r["subject"],
                "predicate": r["predicate"],
                "object": r["object"],
                "confidence": r["confidence"],
            })
    # 工作记忆
    scratch = {}
    with get_conn() as conn:
        cursor = conn.cursor()
        for key in ["_scratch_currently", "_scratch_mood", "_scratch_goal"]:
            cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row and row["value"]:
                scratch[key.replace("_scratch_", "")] = row["value"]
    # 滚动摘要
    rolling = ""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key = '_rolling_summary'")
        row = cursor.fetchone()
        if row:
            rolling = row["value"]
    # 关键信息
    keypoints = get_all_active_keypoints()
    # 摘要
    summaries = [s["summary"] for s in (get_active_tiered_summaries() or [])]
    return {
        "profile": profile,
        "facts": facts,
        "entities": entities,
        "knowledge": knowledge,
        "scratch": scratch,
        "rolling_summary": rolling,
        "keypoints": keypoints,
        "summaries": summaries,
    }

@router.delete("/vault/{vtype}")
async def delete_memory_item(vtype: str, key: str = ""):
    """删除特定类型的记忆（key 通过 query 参数传递，避免路径编码问题）"""
    from core.db import get_conn
    if vtype == "profile":
        if not key:
            return {"status": "error", "message": "key 不能为空"}
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_profile WHERE key=?", (key,))
            # 清理关联的实体记录
            if key.startswith("_fact_"):
                cursor.execute("SELECT id, linked_memories FROM entities")
                for row in cursor.fetchall():
                    try:
                        import json
                        linked = set(json.loads(row["linked_memories"]) if row["linked_memories"] else [])
                        if key in linked:
                            linked.discard(key)
                            if linked:
                                cursor.execute("UPDATE entities SET linked_memories = ? WHERE id = ?",
                                              (json.dumps(list(linked)), row["id"]))
                            else:
                                cursor.execute("DELETE FROM entities WHERE id = ?", (row["id"]))
                    except Exception:
                        pass
            # 清除画像缓存
            from core.profile_builder import clear_profile_cache
            clear_profile_cache()
    elif vtype == "summary":
        if not key or len(key.strip()) < 2:
            return {"status": "error", "message": "key 至少需要2个字符"}
        with get_conn() as conn:
            escaped_key = key.replace('%', '\\%').replace('_', '\\_')
            conn.cursor().execute("DELETE FROM tiered_summary WHERE summary LIKE ? ESCAPE '\\'", (f"%{escaped_key}%",))
    else:
        return {"status": "error", "message": f"未知的记忆类型: {vtype}"}
    return {"status": "ok"}


@router.post("/profile/cleanup")
async def cleanup_profile(days: int = 90):
    from core.profile_builder import cleanup_expired_profile
    deleted = cleanup_expired_profile(days)
    return {"status": "ok", "deleted": deleted}

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

    recent_text = "\n".join([f"{'用户' if r['role']=='user' else '「' + ai_name + '」'}: {r['content'][:100]}" for r in reversed(recent)])
    prompt = f"今天是{today}。「{ai_name}」和用户今天聊了{msg_count}条消息。以下是今天的一些对话片段：\n{recent_text}\n\n请以「{ai_name}」的第一人称视角写一篇简短的日记（100字以内），内容包括：今天和用户聊了什么、自己的感受、用户今天的心情。语气温暖自然。"

    loop = asyncio.get_running_loop()
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
        cursor.execute("SELECT key, value FROM user_profile WHERE extracted_at >= ? AND key NOT LIKE '_fact_%' ORDER BY extracted_at DESC LIMIT 10", (today,))
        _game_words = ["游戏", "2048", "扫雷", "贪吃蛇", "得分", "最高分", "通关", "刷新"]
        new_profile = [{"key": _human_label(r["key"]), "_key": r["key"], "label": _human_label(r["key"]), "value": _human_value(r["value"])} for r in cursor.fetchall()
                       if not any(w in (r["key"] + r["value"]) for w in _game_words)]
        # 今天的关键信息从摘要中提取
        cursor.execute("SELECT summary, key_points FROM tiered_summary WHERE created_at >= ? ORDER BY id DESC LIMIT 3", (today,))
        new_summaries = [{"summary": r["summary"][:200], "key_points": r["key_points"]} for r in cursor.fetchall()]
    has_new = bool(new_profile or new_summaries)
    return {"has_new": has_new, "new_profile": new_profile, "new_summaries": new_summaries}