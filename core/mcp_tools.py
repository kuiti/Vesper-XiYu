"""MCP 工具注册表 —— 将现有 DB 函数封装为标准 JSON-RPC 工具"""

from core.db import (
    get_memory,
    get_todos as _get_todos, add_todo,
    get_notes as _get_notes, add_note,
    get_reminders as _get_reminders, add_reminder,
    search_chat_messages, get_config,
)

TOOLS = [
    {
        "name": "search_memory",
        "description": "搜索用户记忆和对话记忆，返回相关记忆内容",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "搜索关键词"}},
            "required": ["query"]
        }
    },
    {
        "name": "get_todos",
        "description": "获取所有待办事项列表",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "add_todo",
        "description": "添加新的待办事项",
        "inputSchema": {
            "type": "object",
            "properties": {"task": {"type": "string", "description": "待办内容"}},
            "required": ["task"]
        }
    },
    {
        "name": "get_notes",
        "description": "获取所有笔记列表",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "add_note",
        "description": "添加新的笔记",
        "inputSchema": {
            "type": "object",
            "properties": {"title": {"type": "string"}, "content": {"type": "string"}},
            "required": ["content"]
        }
    },
    {
        "name": "get_reminders",
        "description": "获取所有提醒列表",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "search_chat",
        "description": "全文搜索聊天记录",
        "inputSchema": {
            "type": "object",
            "properties": {"keyword": {"type": "string", "description": "搜索关键词"}},
            "required": ["keyword"]
        }
    },
]


def call_tool(name, arguments):
    """执行工具调用，返回结果字符串"""
    for tool in TOOLS:
        if tool["name"] == name:
            for req in tool["inputSchema"].get("required", []):
                if req not in arguments:
                    return f"缺少必需参数: {req}"
            break
    if name == "search_memory":
        mems = get_memory()
        query = arguments.get("query", "").lower()
        results = [f"{k}: {v}" for k, v in mems.items() if query in k.lower() or query in v.lower()]
        return "\n".join(results[:5]) if results else "无相关记忆"

    if name == "get_todos":
        todos = _get_todos()
        if not todos:
            return "暂无待办"
        return "\n".join([f"[{'✓' if t['done'] else ' '}] {t['task']}" for t in todos])

    if name == "add_todo":
        add_todo(arguments["task"])
        return "待办已添加"

    if name == "get_notes":
        notes = _get_notes()
        if not notes:
            return "暂无笔记"
        return "\n".join([f"- {n.get('title') or (n.get('content') or '')[:30]}" for n in notes])

    if name == "add_note":
        add_note(arguments.get("title", ""), arguments["content"])
        return "笔记已添加"

    if name == "get_reminders":
        reminders = _get_reminders()
        if not reminders:
            return "暂无提醒"
        return "\n".join([f"- {r['content']} ({r.get('target_time','')})" for r in reminders])

    if name == "search_chat":
        results = search_chat_messages(arguments["keyword"])
        if not results:
            return "无匹配聊天记录"
        return "\n".join([f"[{r['role']}] {r['content'][:100]}" for r in results[:5]])

    return f"未知工具: {name}"
