from fastapi import APIRouter, Query
from core.db import search_chat_messages
from typing import List, Dict, Any

router = APIRouter(prefix="/search", tags=["search"])

@router.get("/chat")
async def search_chat(q: str = Query(..., min_length=1), limit: int = 20) -> List[Dict[str, Any]]:
    """全文搜索聊天记录"""
    return search_chat_messages(q, limit)