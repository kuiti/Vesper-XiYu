"""示例插件 —— 展示插件系统支持的所有功能"""


def register():
    """返回插件信息。

    支持字段：
    - name: 工具名（function calling 用）
    - description: 工具描述
    - handler: 执行函数，接收 arguments: dict
    - parameters: OpenAI function calling 格式的参数定义
    - commands: /命令 别名列表
    """
    return {
        "name": "example",
        "description": "示例工具——演示插件系统用法",
        "handler": handle_example,
        "parameters": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "要回显的消息"},
            },
        },
        "required": ["message"],
        "commands": ["/example", "/hello"],
    }


def handle_example(args: dict) -> str:
    """插件的主逻辑"""
    msg = args.get("message", "world")
    return f"插件收到: {msg}"



# ─── 更复杂的插件示例：调用数据库 ───

"""
# plugins/weather.py
import requests

def register():
    return {
        "name": "weather",
        "description": "查询天气",
        "handler": handle_weather,
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名"},
            },
        },
        "required": ["city"],
        "commands": ["/weather"],
    }

def handle_weather(args):
    city = args.get("city", "北京")
    # 调用天气 API
    return f"{city}的天气：晴，25°C"
"""


"""
# plugins/custom_greeting.py

def register():
    return {
        "name": "greeting",
        "description": "自定义打招呼",
        "handler": handle_greeting,
        "parameters": {
            "type": "object",
            "properties": {
                "style": {"type": "string", "enum": ["warm", "cool", "funny"]},
            },
        },
        "commands": ["/greet"],
    }

def handle_greeting(args):
    style = args.get("style", "warm")
    greetings = {"warm": "你好呀~", "cool": "哟。", "funny": "嘿！又见面了！"}
    return greetings.get(style, "你好~")
"""
