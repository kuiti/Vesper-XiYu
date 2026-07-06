# core/config_keys.py — 配置键常量
"""消除散落的 get_config("xxx") 字符串拼写错误风险。
只声明高频使用的核心配置键。"""
from __future__ import annotations

# ─── Token 预算 ───
TOKEN_BUDGET_CHARS: int = 14000