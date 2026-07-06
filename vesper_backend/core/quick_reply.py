# core/quick_reply.py — 快捷命令链
"""一键触发多步操作"""
from core.db import get_config, set_config
import json
import logging

logger = logging.getLogger(__name__)

DEFAULT_QUICK_REPLIES = [
    {"name": "早安", "commands": ["查天气", "报日程", "说早安"]},
    {"name": "晚安", "commands": ["道晚安"]},
    {"name": "今天怎么样", "commands": ["问近况"]},
]


def get_quick_replies() -> list:
    """获取快捷回复列表"""
    raw = get_config("quick_phrases", "[]")
    try:
        replies = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(replies, list):
            return replies if replies else DEFAULT_QUICK_REPLIES
    except (json.JSONDecodeError, TypeError):
        pass
    return DEFAULT_QUICK_REPLIES


def save_quick_replies(replies: list):
    """保存快捷回复列表"""
    set_config("quick_phrases", json.dumps(replies, ensure_ascii=False))
