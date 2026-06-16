from fastapi import APIRouter
from core.db import get_all_chat_messages, get_config
from typing import Dict, Any
import json

router = APIRouter(prefix="/export", tags=["export"])

@router.get("/chat")
async def export_chat(format: Literal["json", "txt", "md"] = "json") -> Dict[str, Any]:
    """导出聊天记录，支持 json / txt / md 格式"""
    messages = get_all_chat_messages()
    ai_name = get_config("ai_name", "AI")
    user_name = get_config("user_name", "我")

    if format == "json":
        content = json.dumps(messages, ensure_ascii=False, indent=2)
        filename = "chat_history.json"
        content_type = "application/json"
    elif format == "md" or format == "markdown":
        lines = [f"# {ai_name} 聊天记录\n"]
        lines.append(f"导出时间：{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n---\n")
        for msg in messages:
            role_label = f"**{user_name}**" if msg['role'] == 'user' else f"**{ai_name}**"
            ts = (msg.get('timestamp') or '')[:19]
            lines.append(f"> {role_label} _{ts}_\n\n{msg.get('content', '')}\n\n---\n")
        content = "\n".join(lines)
        filename = "chat_history.md"
        content_type = "text/markdown"
    else:
        lines = []
        for msg in messages:
            ts = msg.get('timestamp') or ''
            lines.append(f"[{ts}] {msg['role']}: {msg.get('content', '')}\n")
        content = "".join(lines)
        filename = "chat_history.txt"
        content_type = "text/plain"

    return {
        "filename": filename,
        "content": content,
        "content_type": content_type
    }