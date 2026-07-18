# core/plugin_loader.py — 插件系统
"""插件系统：plugins/ 目录下的 .py 文件自动注册为工具。

每个插件提供 register() 函数，返回以下格式：

    {
        "name": "tool_name",           # 工具名（function calling 用）
        "description": "工具描述",
        "openai_tool": {...},           # OpenAI function calling 格式（可选）
        "handler": callable,           # 执行函数，接收 arguments: dict
        "commands": ["/cmd1", "/cmd2"], # 文本命令别名（可选）
    }

内置工具通过 _register_builtins() 同样注册，与插件无区别。
"""

import os
import importlib.util
import logging

logger = logging.getLogger(__name__)

# ─── 注册表 ───

_tool_registry: dict[str, dict] = {}  # name -> plugin_info
_command_registry: dict[str, str] = {}  # /command -> tool_name


def discover_plugins():
    """扫描 plugins/ 目录，加载所有插件"""
    plugin_dir = os.path.join(os.path.dirname(__file__), '..', 'plugins')
    os.makedirs(plugin_dir, exist_ok=True)

    for f in sorted(os.listdir(plugin_dir)):
        if f.endswith('.py') and not f.startswith('_'):
            name = f[:-3]
            path = os.path.join(plugin_dir, f)
            try:
                spec = importlib.util.spec_from_file_location(name, path)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    if hasattr(mod, 'register'):
                        info = mod.register()
                        _register_tool(name, info)
                        logger.info(f"[插件] 已加载: {name}")
            except Exception as e:
                logger.warning(f"[插件] 加载失败 {name}: {e}")


def _register_tool(name: str, info: dict):
    """注册一个工具到注册表"""
    _tool_registry[name] = info

    # 注册命令别名
    for cmd in info.get("commands", []):
        _command_registry[cmd] = name


def register_builtin(name: str, info: dict):
    """供 mcp_tools 注册内置工具"""
    _register_tool(name, info)


# ─── 查询 ───

def get_tool_names() -> list[str]:
    """返回所有已注册工具的名称列表"""
    return list(_tool_registry.keys())


def get_all_openai_tools() -> list[dict]:
    """返回所有已注册工具的 OpenAI function calling 格式"""
    tools = []
    for name, info in _tool_registry.items():
        if "openai_tool" in info:
            tools.append(info["openai_tool"])
        else:
            tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": info.get("description", ""),
                    "parameters": info.get("parameters", {
                        "type": "object",
                        "properties": {}
                    }),
                }
            })
    return tools


def get_all_mcp_tools() -> list[dict]:
    """返回所有已注册工具的 MCP JSON-RPC 格式"""
    tools = []
    for name, info in _tool_registry.items():
        tools.append({
            "name": name,
            "description": info.get("description", ""),
            "inputSchema": info.get("input_schema", {
                "type": "object",
                "properties": {}
            }),
        })
    return tools


def call_tool(name: str, arguments: dict) -> str:
    """执行工具调用，遍历注册表 + 命令别名"""
    # 安全校验
    from core.security import detect_sql_injection, detect_path_traversal, sanitize_display_text
    for k, v in arguments.items():
        if isinstance(v, str):
            if detect_sql_injection(v):
                return f"安全拒绝: 参数 {k} 包含 SQL 注入模式"
            if detect_path_traversal(v):
                return f"安全拒绝: 参数 {k} 包含路径遍历模式"
            arguments[k] = sanitize_display_text(v, max_length=5000)

    # 检查工具名
    info = _tool_registry.get(name)
    if not info:
        return f"未知工具: {name}"

    # 调用 handler
    handler = info.get("handler")
    if not handler:
        return f"工具 {name} 未实现 handler"

    try:
        result = handler(arguments)
        return str(result) if result is not None else "ok"
    except Exception as e:
        logger.warning(f"[插件] 工具 {name} 执行失败: {e}")
        return f"执行失败: {e}"


def handle_command(cmd: str, args: str = "") -> str | None:
    """处理文本命令（如内置命令）"""
    name = _command_registry.get(cmd)
    if not name:
        return None
    return call_tool(name, {"args": args})


def get_command_help() -> str:
    """返回所有可用命令的帮助文本"""
    lines = []
    for cmd, name in sorted(_command_registry.items()):
        info = _tool_registry.get(name, {})
        desc = info.get("description", "")
        lines.append(f"{cmd} — {desc}")
    return "\n".join(lines)


# 启动时自动扫描
discover_plugins()
