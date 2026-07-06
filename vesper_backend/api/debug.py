"""调试模块 —— 记录并查看发送给 LLM 的最近 prompt。"""
from fastapi import APIRouter
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/debug", tags=["debug"])

_prompt_history: list[str] = []


def log_prompt(prompt: str):
    """记录 prompt（由 llm_client 调用）"""
    _prompt_history.append(prompt)
    if len(_prompt_history) > 10:
        _prompt_history.pop(0)


@router.get("/prompts")
async def get_recent_prompts():
    """获取最近 10 条发送给 LLM 的 prompt"""
    return {"prompts": _prompt_history}
