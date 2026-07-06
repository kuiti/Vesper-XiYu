"""MCP 工具注册表 —— 通过 plugin_loader 统一注册内置工具 + 插件工具"""

from core.plugin_loader import (
    register_builtin,
    get_all_openai_tools as _get_openai,
    get_all_mcp_tools as _get_mcp,
    call_tool as _call_tool,
    discover_plugins,
)
from core.db import (
    get_memory, search_chat_messages, get_config, set_config, get_conn,
)
from core.security import detect_sql_injection, detect_path_traversal, sanitize_display_text
import logging
from core.retry import silent_exc
import json
import hashlib
from datetime import datetime

logger = logging.getLogger(__name__)


def _make_openai_tool(name: str, desc: str, properties: dict, required: list = None) -> dict:
    """简化构建 OpenAI function calling 格式"""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {
                "type": "object",
                "properties": properties,
            },
            "required" if required else "_": required or [],
        }
    }


def _make_mcp_tool(name: str, desc: str, properties: dict, required: list = None) -> dict:
    """简化构建 MCP 格式"""
    return {
        "name": name,
        "description": desc,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required" if required else "_": required or [],
        }
    }


# ─── 内置工具 handler ───

def _handle_search_memory(args: dict) -> str:
    """搜索用户记忆（向量 + 关键词双通道）"""
    query = args.get("query", "")
    try:
        from core.vector_store import search_memories, is_model_ready
        if is_model_ready():
            vec_results = search_memories(query, top_k=5)
            if vec_results:
                lines = []
                for r in vec_results:
                    label = "📌" if r.get("type") == "profile" else "💭"
                    lines.append(f"{label} {r['key']}: {r['value'][:200]}")
                return "\n".join(lines)
    except Exception as e:
        silent_exc("call_tool.search_memory", e)
    mems = get_memory()
    query_lower = query.lower()
    results = [f"{k}: {v}" for k, v in mems.items() if query_lower in k.lower() or query_lower in v.lower()]
    return "\n".join(results[:5]) if results else "无相关记忆"


def _handle_update_scratch(args: dict) -> str:
    """更新工作记忆（当前状态/情绪/目标）"""
    from core.prompt_builder import update_scratch
    update_scratch(
        currently=args.get("currently"),
        mood=args.get("mood"),
        goal=args.get("goal"),
    )
    return "工作记忆已更新"


def _handle_declare_memory_intent(args: dict) -> str:
    """声明记忆意图，高置信度时写入用户画像"""
    kind = args.get("kind") or args.get("category", "memory")
    summary = args.get("summary") or args.get("fact", "")
    confidence = args.get("confidence", 0.5)
    if not summary:
        return "未提供要记住的内容"
    if confidence >= 0.8:
        fact_hash = hashlib.sha256(summary.encode()).hexdigest()
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM user_profile WHERE key = ?", (f"_fact_{fact_hash}",))
            if not cursor.fetchone():
                cursor.execute(
                    "REPLACE INTO user_profile (key, value, confidence, extracted_at) VALUES (?, ?, ?, ?)",
                    (f"_fact_{fact_hash}", json.dumps({
                        "text": summary, "category": kind,
                        "importance": int(confidence * 10),
                        "created_at": datetime.now().isoformat()
                    }, ensure_ascii=False), confidence, datetime.now().isoformat())
                )
                from core.profile_builder import clear_profile_cache, extract_entities_from_text, upsert_entity
                clear_profile_cache()
                fact_key = f"_fact_{fact_hash}"
                entities = extract_entities_from_text(summary)
                for entity_text, entity_type in entities:
                    upsert_entity(entity_text, entity_type, fact_key)
                return f"已记住: {summary}"
        return f"已存在: {summary}"
    return f"置信度过低({confidence})，未保存"


def _handle_add_countdown(args: dict) -> str:
    """添加倒计时"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO countdowns (name, target_date) VALUES (?, ?)",
            (args["name"], args["target_date"]),
        )
        conn.commit()
    return f"倒计时已添加: {args['name']}"


def _handle_get_countdowns(args: dict) -> str:
    """获取所有倒计时列表"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, target_date FROM countdowns ORDER BY target_date")
        rows = cursor.fetchall()
    if not rows:
        return "暂无倒计时"
    return "\n".join([f"- {r['name']} ({r['target_date']})" for r in rows])


def _handle_delete_countdown(args: dict) -> str:
    """删除指定倒计时"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM countdowns WHERE id = ?", (args["id"],))
        conn.commit()
    return "倒计时已删除"


def _handle_add_goal(args: dict) -> str:
    """添加目标"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO goal_tracking (goal_text, category, status, first_mentioned, last_mentioned) VALUES (?, ?, 'active', datetime('now'), datetime('now'))",
            (args["goal_text"], args.get("category", "生活")),
        )
        conn.commit()
    return f"目标已添加: {args['goal_text']}"


def _handle_get_goals(args: dict) -> str:
    """获取所有活跃目标"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, goal_text, category, status FROM goal_tracking WHERE status = 'active' ORDER BY created_at DESC LIMIT 20")
        rows = cursor.fetchall()
    if not rows:
        return "暂无进行中的目标"
    return "\n".join([f"- [{r['category']}] {r['goal_text']}" for r in rows])


def _handle_delete_goal(args: dict) -> str:
    """标记目标为已完成"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE goal_tracking SET status = 'completed' WHERE id = ?", (args["id"],))
        conn.commit()
    return "目标已完成"


def _handle_search_chat(args: dict) -> str:
    """搜索聊天记录"""
    query = args.get("query", "")
    limit = args.get("limit", 5)
    character_id = 0
    try:
        from core.character_card import CharacterCard
        card = CharacterCard.get_active()
        if card and hasattr(card, '_db_id') and card._db_id:
            character_id = card._db_id
    except Exception:
        pass
    results = search_chat_messages(query, limit=limit, character_id=character_id)
    if not results:
        return "无相关聊天记录"
    return "\n".join([f"{r.get('content', '')[:200]}" for r in results])


def _handle_update_background(args: dict) -> str:
    """更新 AI 背景设定"""
    action = args.get("action", "add")
    key = args.get("key", "")
    value = args.get("value", "")
    from core.profile_builder import update_background_item
    update_background_item(action, key, value)
    return f"背景已更新: {key}"


# ─── 注册所有内置工具 ───

BUILTIN_TOOLS = [
    {
        "name": "search_memory",
        "description": "搜索用户记忆和对话记忆",
        "handler": _handle_search_memory,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"}
            },
        },
        "required": ["query"],
        "commands": ["/search"],
    },
    {
        "name": "search_chat",
        "description": "搜索聊天记录",
        "handler": _handle_search_chat,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "limit": {"type": "integer", "description": "返回条数"},
            },
        },
        "required": ["query"],
        "commands": ["/chatsearch"],
    },
    {
        "name": "update_scratch",
        "description": "更新工作记忆——记录用户当前状态、情绪或目标",
        "handler": _handle_update_scratch,
        "parameters": {
            "type": "object",
            "properties": {
                "currently": {"type": "string", "description": "用户当前状态"},
                "mood": {"type": "string", "description": "用户当前情绪"},
                "goal": {"type": "string", "description": "用户当前目标"},
            },
        },
    },
    {
        "name": "declare_memory_intent",
        "description": "声明你注意到的关于用户的信息，需要被记住",
        "handler": _handle_declare_memory_intent,
        "parameters": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["memory", "preference", "fact", "emotion"], "description": "信息类型"},
                "summary": {"type": "string", "description": "要记住的内容（一句话）"},
                "confidence": {"type": "number", "description": "置信度 0-1"},
            },
        },
        "required": ["kind", "summary", "confidence"],
    },
    {
        "name": "add_countdown",
        "description": "添加倒计时（距离某天还有多少天）",
        "handler": _handle_add_countdown,
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "倒计时名称"},
                "target_date": {"type": "string", "description": "目标日期（YYYY-MM-DD）"},
            },
        },
        "required": ["name", "target_date"],
        "commands": ["/countdown"],
    },
    {
        "name": "get_countdowns",
        "description": "获取所有倒计时列表",
        "handler": _handle_get_countdowns,
        "parameters": {"type": "object", "properties": {}},
        "commands": ["/countdowns"],
    },
    {
        "name": "delete_countdown",
        "description": "删除倒计时",
        "handler": _handle_delete_countdown,
        "parameters": {
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "倒计时ID"}},
        },
        "required": ["id"],
    },
    {
        "name": "add_goal",
        "description": "添加目标（学习目标、健身目标等）",
        "handler": _handle_add_goal,
        "parameters": {
            "type": "object",
            "properties": {
                "goal_text": {"type": "string", "description": "目标内容"},
                "category": {"type": "string", "description": "类别（学习/健身/工作/生活等）"},
            },
        },
        "required": ["goal_text"],
        "commands": ["/goal"],
    },
    {
        "name": "get_goals",
        "description": "获取所有目标列表",
        "handler": _handle_get_goals,
        "parameters": {"type": "object", "properties": {}},
        "commands": ["/goals"],
    },
    {
        "name": "delete_goal",
        "description": "删除目标",
        "handler": _handle_delete_goal,
        "parameters": {
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "目标ID"}},
        },
        "required": ["id"],
    },
    {
        "name": "update_background",
        "description": "更新AI背景设定（昵称、外号、角色关系、用户偏好等）",
        "handler": _handle_update_background,
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["add", "replace", "remove"]},
                "key": {"type": "string", "description": "背景类别"},
                "value": {"type": "string", "description": "内容"},
            },
        },
        "required": ["action", "key"],
    },
]

# 注册所有内置工具
for tool in BUILTIN_TOOLS:
    name = tool["name"]
    # 构建 openai_tool
    openai_tool = _make_openai_tool(
        name, tool["description"],
        tool["parameters"]["properties"],
        tool.get("required"),
    )
    # 构建 input_schema（MCP 格式）
    input_schema = {
        "type": "object",
        "properties": tool["parameters"]["properties"],
    }
    if tool.get("required"):
        input_schema["required"] = tool["required"]

    register_builtin(name, {
        "name": name,
        "description": tool["description"],
        "handler": tool["handler"],
        "openai_tool": openai_tool,
        "input_schema": input_schema,
        "commands": tool.get("commands", []),
        "parameters": tool["parameters"],
    })


# ─── 向后兼容导出（旧代码仍能 from core.mcp_tools import OPENAI_TOOLS, TOOLS, call_tool）───
call_tool = _call_tool


def __getattr__(name):
    if name == "OPENAI_TOOLS":
        return _get_openai()
    if name == "TOOLS":
        return _get_mcp()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
