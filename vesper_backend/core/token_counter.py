# core/token_counter.py — 简易 token 计数器
"""基于字符估算，不用 tiktoken 省依赖"""


def estimate_tokens(text: str) -> int:
    """估算 token 数：中文约1.5字符/token，英文约4字符/token"""
    if not text:
        return 0
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)


def count_prompt(prompt: str) -> dict:
    """统计 prompt 的 token 消耗"""
    return {
        "total_tokens": estimate_tokens(prompt),
        "characters": len(prompt),
    }
