"""记忆管理 API — 提供手动记忆、记忆保险箱、AI日记、今日学习等功能（per-character）。"""
from fastapi import APIRouter, Query
from core.db import get_memory, set_memory, delete_memory, get_chat_conn, get_conn
from pydantic import BaseModel
from typing import Dict
import json as _json
import logging
from core.retry import silent_exc
logger = logging.getLogger(__name__)

_PROFILE_KEY_LABELS = {
    "user_student": "身份", "user_habit_stay_up": "习惯", "user_habit": "习惯",
    "name": "名字", "user_name": "称呼", "city": "城市", "gender": "性别", "age": "年龄",
    "occupation": "职业", "hobby": "爱好", "personality": "性格", "language": "语言",
}

def _human_label(key: str) -> str:
    """将内部 profile key 转换为人类可读的中文标签。"""
    if key in _PROFILE_KEY_LABELS:
        return _PROFILE_KEY_LABELS[key]
    return key.replace("user_", "").replace("_", " ")

def _human_value(val: str) -> str:
    """将 JSON 格式的 profile value 提取为可读文本。"""
    if not val:
        return ""
    try:
        obj = _json.loads(val)
        if isinstance(obj, dict):
            return obj.get("text") or obj.get("value") or obj.get("name") or obj.get("summary") or str(obj)
    except (_json.JSONDecodeError, TypeError) as e:
        silent_exc("memory", e)
    return val

router = APIRouter(prefix="/memory", tags=["memory"])

class MemoryItem(BaseModel):
    key: str
    value: str

@router.get("/")
async def list_memory(character_id: int = Query(0, description="角色 ID，默认 0")) -> Dict[str, str]:
    """获取手动记忆（per-character）"""
    all_mem = get_memory(character_id=character_id)
    return {k: v for k, v in all_mem.items() if not k.startswith("_")}

@router.post("/")
async def add_memory(item: MemoryItem,
                     character_id: int = Query(0, description="角色 ID，默认 0")):
    """添加或更新一条手动记忆（per-character）"""
    set_memory(item.key, item.value, character_id=character_id)
    return {"status": "ok"}

@router.delete("/{key}")
async def remove_memory(key: str,
                        character_id: int = Query(0, description="角色 ID，默认 0")):
    """删除指定 key 的手动记忆（per-character）"""
    delete_memory(key, character_id=character_id)
    return {"status": "ok"}

@router.get("/vault")
async def memory_vault(character_id: int = Query(0, description="角色 ID，默认 0")):
    """记忆保险箱（per-character）"""
    from core.db import get_active_tiered_summaries, get_all_active_keypoints, get_char_config
    import json

    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        # 用户画像
        cursor.execute("SELECT key, value, confidence, extracted_at FROM user_profile WHERE key NOT LIKE '_fact_%' AND key NOT LIKE '_event_%' AND key NOT LIKE '_plan_%' AND key NOT LIKE '_progress_%' ORDER BY confidence DESC")
        profile = [{"key": _human_label(r["key"]), "raw_key": r["key"], "value": _human_value(r["value"]), "confidence": r["confidence"], "extracted_at": r["extracted_at"]} for r in cursor.fetchall()]
        # 原子事实
        facts = []
        cursor.execute("SELECT key, value, confidence, extracted_at FROM user_profile WHERE key LIKE '_fact_%' ORDER BY extracted_at DESC")
        for r in cursor.fetchall():
            try:
                d = json.loads(r["value"])
                facts.append({"key": r["key"], "text": d.get("text", ""), "category": d.get("category", ""), "importance": d.get("importance", 5), "confidence": r["confidence"], "extracted_at": r["extracted_at"]})
            except Exception as e:
                silent_exc("memory_vault", e)
        # 实体
        entities = []
        cursor.execute("SELECT entity_text, entity_type, linked_memories, created_at FROM entities ORDER BY created_at DESC LIMIT 50")
        for r in cursor.fetchall():
            try:
                linked = json.loads(r["linked_memories"]) if r["linked_memories"] else []
            except Exception:
                linked = []
            entities.append({"text": r["entity_text"], "type": r["entity_type"], "linked_count": len(linked), "created_at": r["created_at"]})
        # 知识图谱
        knowledge = []
        cursor.execute("SELECT subject, predicate, object, confidence FROM knowledge_graph ORDER BY confidence DESC LIMIT 30")
        for r in cursor.fetchall():
            knowledge.append({"subject": r["subject"], "predicate": r["predicate"], "object": r["object"], "confidence": r["confidence"]})
        # 工作记忆（per-character config）
        scratch = {}
        for key in ["_scratch_currently", "_scratch_mood", "_scratch_goal"]:
            val = get_char_config(key, character_id=character_id, default="")
            if val:
                scratch[key.replace("_scratch_", "")] = val
        # 滚动摘要（per-character config）
        rolling = get_char_config("_rolling_summary", character_id=character_id, default="")

    keypoints = get_all_active_keypoints(character_id=character_id)
    summaries = [s["summary"] for s in (get_active_tiered_summaries(character_id=character_id) or [])]
    return {"profile": profile, "facts": facts, "entities": entities, "knowledge": knowledge, "scratch": scratch, "rolling_summary": rolling, "keypoints": keypoints, "summaries": summaries}

@router.delete("/vault/{vtype}")
async def delete_memory_item(vtype: str, key: str = "",
                             character_id: int = Query(0, description="角色 ID，默认 0")):
    """删除特定类型的记忆（per-character）"""
    if vtype == "profile":
        if not key:
            return {"status": "error", "message": "key 不能为空"}
        with get_chat_conn(character_id) as conn:
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
                    except Exception as e:
                        silent_exc("delete_memory_item", e)
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
    """清理指定天数前过期的用户画像数据。"""
    from core.profile_builder import cleanup_expired_profile
    deleted = cleanup_expired_profile(days)
    return {"status": "ok", "deleted": deleted}

# ─── AI 日记 ───

@router.get("/diary")
async def get_diary(limit: int = 30):
    """获取最近 N 篇 AI 日记。"""
    from core.db import get_diary_entries
    return get_diary_entries(limit)

@router.post("/diary/generate")
async def generate_diary():
    """手动触发 AI 日记生成（使用共享日记工具模块）"""
    import asyncio
    from datetime import datetime
    from core.diary_utils import get_today_messages, detect_mood, build_diary_prompt, generate_diary_content
    from core.db import save_diary_entry, get_config

    today = datetime.now().strftime("%Y-%m-%d")
    ai_name = get_config("ai_name", "夕语")
    user_name = get_config("user_name", "用户")

    msg_count, today_msgs, yest_row = get_today_messages()
    if msg_count < 3:
        return {"ok": False, "message": f"今天只聊了{msg_count}条，太少了写不出日记"}

    all_text = " ".join(r["content"] for r in today_msgs)
    detected_mood = detect_mood(all_text)
    yesterday_mood = yest_row["mood"] if yest_row else None
    prompt = build_diary_prompt(today, msg_count, today_msgs, ai_name, user_name, yesterday_mood)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, lambda: generate_diary_content(prompt))
    if result:
        save_diary_entry(today, result, detected_mood)
        return {"ok": True, "content": result, "mood": detected_mood, "date": today}
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