"""搜索 API — 提供聊天记录全文搜索功能。"""
from fastapi import APIRouter, Query
from core.db import search_chat_messages
from typing import List, Dict, Any, Optional

router = APIRouter(prefix="/search", tags=["search"])

@router.get("/chat")
async def search_chat(q: str = Query(..., min_length=1), limit: int = 20, character_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """全文搜索聊天记录"""
    return search_chat_messages(q, limit, character_id=character_id or 0)