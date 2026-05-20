from fastapi import APIRouter
from core.db import get_all_chat_messages
from typing import Dict, Any
import json

router = APIRouter(prefix="/export", tags=["export"])

@router.get("/chat")
async def export_chat(format: str = "json") -> Dict[str, Any]:
    """导出聊天记录，支持 json 和 txt 格式"""
    messages = get_all_chat_messages()
    
    if format == "json":
        content = json.dumps(messages, ensure_ascii=False, indent=2)
        filename = "chat_history.json"
        content_type = "application/json"
    else:
        lines = []
        for msg in messages:
            lines.append(f"[{msg['timestamp']}] {msg['role']}: {msg['content']}\n")
        content = "".join(lines)
        filename = "chat_history.txt"
        content_type = "text/plain"
    
    return {
        "filename": filename,
        "content": content,
        "content_type": content_type
    }