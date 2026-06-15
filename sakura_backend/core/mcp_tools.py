"""MCP 工具注册表 —— 将现有 DB 函数封装为标准 JSON-RPC 工具 + OpenAI Function Calling 格式"""

from core.db import (
    get_memory,
    get_todos as _get_todos, add_todo,
    get_notes as _get_notes, add_note,
    get_reminders as _get_reminders, add_reminder, delete_reminder,
    search_chat_messages, get_config, set_config,
    get_conn,
)
from core.security import detect_sql_injection, detect_path_traversal, sanitize_display_text
import logging
from core.retry import silent_exc
logger = logging.getLogger(__name__)

# ─── OpenAI Function Calling 格式 ───
OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_reminder",
            "description": "添加提醒事项（考试、约会、重要日期等）",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "提醒内容"},
                    "target_time": {"type": "string", "description": "目标时间（ISO格式，如2026-06-09T09:00:00）"},
                    "level": {"type": "integer", "description": "重要程度 1-7（7=最高/强制，1=最低/日常）", "default": 4}
                },
                "required": ["content", "target_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_schedule",
            "description": "添加日程/特殊日期（生日、纪念日、节日等）",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "日程标题"},
                    "start_time": {"type": "string", "description": "开始时间（ISO格式）"},
                    "end_time": {"type": "string", "description": "结束时间（可选）"},
                    "description": {"type": "string", "description": "描述（可选）"},
                    "color": {"type": "string", "description": "颜色（可选，默认蓝色）", "default": "#5390d4"}
                },
                "required": ["title", "start_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_todo",
            "description": "添加待办事项",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "待办内容"}
                },
                "required": ["task"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_note",
            "description": "添加笔记",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "笔记标题"},
                    "content": {"type": "string", "description": "笔记内容"}
                },
                "required": ["content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "搜索用户记忆和对话记忆",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_scratch",
            "description": "更新工作记忆——记录用户当前状态、情绪或目标。当你从对话中察觉到用户的状态变化时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "currently": {"type": "string", "description": "用户当前状态（如'准备面试''在旅行''在加班'）"},
                    "mood": {"type": "string", "description": "用户当前情绪（如'开心''焦虑''无聊'）"},
                    "goal": {"type": "string", "description": "用户当前目标（如'减肥''学Python''找新工作'）"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "declare_memory_intent",
            "description": "声明你注意到的关于用户的信息，需要被记住。当你发现用户的偏好、习惯、重要信息时调用。高置信度(>=0.8)的信息会自动保存。",
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["memory", "preference", "fact", "emotion"], "description": "信息类型"},
                    "summary": {"type": "string", "description": "要记住的内容（一句话）"},
                    "confidence": {"type": "number", "description": "置信度 0-1（0.8以上自动保存）"}
                },
                "required": ["kind", "summary", "confidence"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_countdown",
            "description": "添加倒计时（距离某天还有多少天）",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "倒计时名称"},
                    "target_date": {"type": "string", "description": "目标日期（YYYY-MM-DD格式）"}
                },
                "required": ["name", "target_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_countdowns",
            "description": "获取所有倒计时列表",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_goal",
            "description": "添加目标（学习目标、健身目标等）",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal_text": {"type": "string", "description": "目标内容"},
                    "category": {"type": "string", "description": "类别（学习/健身/工作/生活等）", "default": "生活"}
                },
                "required": ["goal_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_goals",
            "description": "获取所有目标列表",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_todos",
            "description": "获取所有待办事项列表",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_notes",
            "description": "获取所有笔记列表",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_reminders",
            "description": "获取所有提醒列表",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_schedules",
            "description": "获取所有日程列表",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_background",
            "description": "更新AI背景设定（昵称、外号、角色关系、用户偏好等）。当用户说'叫我XX''以后叫你XX''你是我XX'时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["add", "replace", "remove"], "description": "操作类型：add=新增，replace=覆盖已有，remove=删除"},
                    "key": {"type": "string", "description": "背景类别（如 nickname/ai_nickname/role/preference/event/personality）"},
                    "value": {"type": "string", "description": "内容（remove时可省略）"}
                },
                "required": ["action", "key"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_chat",
            "description": "搜索聊天记录",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "limit": {"type": "integer", "description": "返回条数", "default": 5}
                },
                "required": ["query"]
            }
        }
    },
]

# ─── MCP JSON-RPC 格式（兼容旧版）───
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
        "name": "add_reminder",
        "description": "添加新的提醒事项（用于记住重要日期、考试、约会等）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "提醒内容"},
                "target_time": {"type": "string", "description": "目标时间（ISO格式，如2026-06-09T09:00:00）"},
                "level": {"type": "integer", "description": "重要程度 1-7（7=最高/强制，1=最低/日常）", "default": 4}
            },
            "required": ["content", "target_time"]
        }
    },
    {
        "name": "delete_reminder",
        "description": "删除提醒事项",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "提醒ID"}},
            "required": ["id"]
        }
    },
    {
        "name": "add_schedule",
        "description": "添加日程/特殊日期（生日、纪念日、节日等）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "日程标题"},
                "start_time": {"type": "string", "description": "开始时间（ISO格式）"},
                "end_time": {"type": "string", "description": "结束时间（可选）"},
                "description": {"type": "string", "description": "描述（可选）"},
                "color": {"type": "string", "description": "颜色（可选，默认蓝色）", "default": "#5390d4"}
            },
            "required": ["title", "start_time"]
        }
    },
    {
        "name": "get_schedules",
        "description": "获取所有日程列表",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "delete_schedule",
        "description": "删除日程",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "日程ID"}},
            "required": ["id"]
        }
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
    {
        "name": "add_countdown",
        "description": "添加倒计时（距离某天还有多少天）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "倒计时名称"},
                "target_date": {"type": "string", "description": "目标日期（YYYY-MM-DD格式）"}
            },
            "required": ["name", "target_date"]
        }
    },
    {
        "name": "get_countdowns",
        "description": "获取所有倒计时列表",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "delete_countdown",
        "description": "删除倒计时",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "倒计时ID"}},
            "required": ["id"]
        }
    },
    {
        "name": "add_goal",
        "description": "添加目标（学习目标、健身目标等）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal_text": {"type": "string", "description": "目标内容"},
                "category": {"type": "string", "description": "类别（学习/健身/工作/生活等）", "default": "生活"}
            },
            "required": ["goal_text"]
        }
    },
    {
        "name": "get_goals",
        "description": "获取所有目标列表",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "delete_goal",
        "description": "删除目标",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "目标ID"}},
            "required": ["id"]
        }
    },
    {
        "name": "update_scratch",
        "description": "更新工作记忆（当前状态/情绪/目标）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "currently": {"type": "string", "description": "用户当前在做什么"},
                "mood": {"type": "string", "description": "用户当前情绪"},
                "goal": {"type": "string", "description": "用户当前目标"}
            }
        }
    },
    {
        "name": "declare_memory_intent",
        "description": "声明记忆意图：AI 主动保存关于用户的重要信息",
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "description": "信息类型（memory/preference/fact/emotion）"},
                "summary": {"type": "string", "description": "要记住的内容（一句话）"},
                "confidence": {"type": "number", "description": "置信度 0-1"}
            },
            "required": ["kind", "summary", "confidence"]
        }
    },
    {
        "name": "update_background",
        "description": "更新 AI 的背景设定和人物关系信息",
        "inputSchema": {
            "type": "object",
            "properties": {
                "field": {"type": "string", "description": "要更新的字段（role/event/preference/personality/nickname/motivation）"},
                "content": {"type": "string", "description": "字段的新内容"},
                "mode": {"type": "string", "description": "add/remove/replace（默认replace）"}
            },
            "required": ["field", "content"]
        }
    },
]


def call_tool(name, arguments):
    """执行工具调用，返回结果字符串"""
    # 安全校验：含 SQL 注入或路径遍历的输入直接拒绝
    for k, v in arguments.items():
        if isinstance(v, str):
            if detect_sql_injection(v):
                return f"安全拒绝: 参数 {k} 包含 SQL 注入模式"
            if detect_path_traversal(v):
                return f"安全拒绝: 参数 {k} 包含路径遍历模式"
            arguments[k] = sanitize_display_text(v, max_length=5000)

    tool_found = False
    for tool in TOOLS:
        if tool["name"] == name:
            tool_found = True
            for req in tool["inputSchema"].get("required", []):
                if req not in arguments:
                    return f"缺少必需参数: {req}"
            break
    if not tool_found:
        return f"未知工具: {name}"
    if name == "search_memory":
        query = arguments.get("query", "")
        # 向量检索优先
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
            silent_exc("?", e)
        # 降级：关键词检索
        mems = get_memory()
        query_lower = query.lower()
        results = [f"{k}: {v}" for k, v in mems.items() if query_lower in k.lower() or query_lower in v.lower()]
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

    if name == "update_scratch":
        from core.prompt_builder import update_scratch
        update_scratch(
            currently=arguments.get("currently"),
            mood=arguments.get("mood"),
            goal=arguments.get("goal"),
        )
        return "工作记忆已更新"

    if name == "declare_memory_intent":
        kind = arguments.get("kind") or arguments.get("category", "memory")
        summary = arguments.get("summary") or arguments.get("fact", "")
        confidence = arguments.get("confidence", 0.5)
        if not summary:
            return "未提供要记住的内容"
        # 高置信度自动保存
        if confidence >= 0.8:
            import json
            import hashlib
            from datetime import datetime
            fact_hash = hashlib.md5(summary.encode()).hexdigest()
            with get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM user_profile WHERE key = ?", (f"_fact_{fact_hash}",))
                if not cursor.fetchone():
                    cursor.execute(
                        "REPLACE INTO user_profile (key, value, confidence, extracted_at) VALUES (?, ?, ?, ?)",
                        (f"_fact_{fact_hash}", json.dumps({
                            "text": summary,
                            "category": kind,
                            "importance": int(confidence * 10),
                            "created_at": datetime.now().isoformat()
                        }, ensure_ascii=False), confidence, datetime.now().isoformat())
                    )
                    # 清除画像缓存
                    from core.profile_builder import clear_profile_cache, extract_entities_from_text, upsert_entity
                    clear_profile_cache()
                    # 提取实体关联
                    fact_key = f"_fact_{fact_hash}"
                    entities = extract_entities_from_text(summary)
                    for entity_text, entity_type in entities:
                        upsert_entity(entity_text, entity_type, fact_key)
                    return f"已记住: {summary}"
            return f"已存在: {summary}"
        return f"置信度过低({confidence})，未保存"

    if name == "get_reminders":
        reminders = _get_reminders()
        if not reminders:
            return "暂无提醒"
        return "\n".join([f"- {r['content']} ({r.get('target_time','')})" for r in reminders])

    if name == "add_reminder":
        level = arguments.get("level", 4)
        add_reminder(arguments["content"], arguments["target_time"], level)
        return f"提醒已添加: {arguments['content']}"

    if name == "delete_reminder":
        rid = arguments["id"]
        # 智能匹配：如果 id 不是数字，按内容模糊查找
        if not isinstance(rid, int) or rid <= 0:
            rid_str = str(rid)
            with get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, level FROM reminders WHERE content LIKE ? AND done = 0 ORDER BY id DESC LIMIT 1",
                               (f"%{rid_str}%",))
                row = cursor.fetchone()
            if not row:
                return f"未找到包含'{rid_str}'的提醒"
            rid = row["id"]
        # 7级提醒（强制）不能被AI删除，只能用户手动
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT level FROM reminders WHERE id = ?", (rid,))
            row = cursor.fetchone()
        if row and row["level"] >= 7:
            return "该提醒为强制提醒（7级），无法通过AI删除，请手动操作"
        delete_reminder(rid)
        return "提醒已删除"

    if name == "add_schedule":
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO schedule (title, start_time, end_time, description, color) VALUES (?, ?, ?, ?, ?)",
                (
                    arguments["title"],
                    arguments["start_time"],
                    arguments.get("end_time", ""),
                    arguments.get("description", ""),
                    arguments.get("color", "#5390d4"),
                ),
            )
            conn.commit()
        return f"日程已添加: {arguments['title']}"

    if name == "get_schedules":
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, start_time, color FROM schedule ORDER BY start_time DESC LIMIT 20")
            rows = cursor.fetchall()
        if not rows:
            return "暂无日程"
        return "\n".join([f"- {r['title']} ({r['start_time'][:10]})" for r in rows])

    if name == "delete_schedule":
        sid = arguments["id"]
        # 智能匹配：如果 id 不是数字，按标题模糊查找
        if not isinstance(sid, int) or sid <= 0:
            sid_str = str(sid)
            with get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM schedule WHERE title LIKE ? ORDER BY start_time DESC LIMIT 1",
                               (f"%{sid_str}%",))
                row = cursor.fetchone()
            if not row:
                return f"未找到包含'{sid_str}'的日程"
            sid = row["id"]
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM schedule WHERE id = ?", (sid,))
            conn.commit()
        return "日程已删除"

    if name == "update_background":
        import json as _json
        action = arguments.get("action", "add")
        key = arguments.get("key", "")
        value = arguments.get("value", "")
        if not key:
            return "缺少 key 参数"
        current = get_config("ai_background", "")
        bg = {}
        if current:
            try:
                bg = _json.loads(current)
            except _json.JSONDecodeError:
                # 兼容旧格式（纯文本），迁移为结构化
                bg = {"legacy": current}
        if action == "remove":
            if key in bg:
                del bg[key]
                set_config("ai_background", _json.dumps(bg, ensure_ascii=False))
                return f"已移除背景: {key}"
            return f"背景中没有 {key}"
        elif action == "replace":
            bg[key] = value
            set_config("ai_background", _json.dumps(bg, ensure_ascii=False))
            return f"已更新背景: {key} = {value}"
        else:  # add
            if key in bg and bg[key] == value:
                return f"背景已存在: {key} = {value}"
            bg[key] = value
            set_config("ai_background", _json.dumps(bg, ensure_ascii=False))
            return f"已添加背景: {key} = {value}"

    if name == "search_chat":
        keyword = arguments.get("keyword") or arguments.get("query", "")
        results = search_chat_messages(keyword)
        if not results:
            return "无匹配聊天记录"
        return "\n".join([f"[{r['role']}] {r['content'][:100]}" for r in results[:5]])

    if name == "add_countdown":
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO countdowns (name, target_date) VALUES (?, ?)",
                (arguments["name"], arguments["target_date"]),
            )
            conn.commit()
        return f"倒计时已添加: {arguments['name']}"

    if name == "get_countdowns":
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, target_date FROM countdowns ORDER BY target_date")
            rows = cursor.fetchall()
        if not rows:
            return "暂无倒计时"
        return "\n".join([f"- {r['name']} ({r['target_date']})" for r in rows])

    if name == "delete_countdown":
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM countdowns WHERE id = ?", (arguments["id"],))
            conn.commit()
        return "倒计时已删除"

    if name == "add_goal":
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO goal_tracking (goal_text, category, status, first_mentioned, last_mentioned) VALUES (?, ?, 'active', datetime('now'), datetime('now'))",
                (arguments["goal_text"], arguments.get("category", "生活")),
            )
            conn.commit()
        return f"目标已添加: {arguments['goal_text']}"

    if name == "get_goals":
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, goal_text, category, status FROM goal_tracking WHERE status = 'active' ORDER BY created_at DESC LIMIT 20")
            rows = cursor.fetchall()
        if not rows:
            return "暂无进行中的目标"
        return "\n".join([f"- [{r['category']}] {r['goal_text']}" for r in rows])

    if name == "delete_goal":
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE goal_tracking SET status = 'completed' WHERE id = ?", (arguments["id"],))
            conn.commit()
        return "目标已完成"

    return f"未知工具: {name}"
