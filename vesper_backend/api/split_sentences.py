"""智能分句模块 —— AI 识别句子边界 + DFA 状态机本地兜底，处理括号/省略号等复杂场景。"""
# version: 5.0.0
import asyncio
import logging

from fastapi import APIRouter
from pydantic import BaseModel
from core.db import get_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/text", tags=["text"])

class SplitRequest(BaseModel):
    text: str

@router.post("/split")
async def split_sentences(req: SplitRequest):
    """调用 AI 将文本切分为句子数组"""
    text = req.text.strip()
    if not text:
        return {"sentences": []}
    if len(text) < 10:
        return {"sentences": [text]}

    api_key = get_config("api_key", "")
    if not api_key:
        return {"sentences": fallback_split(text)}

    prompt = f"""请将以下角色扮演对话文本切分为独立的句子。规则：
1. 以句号、问号、感叹号、省略号、波浪号结尾的视为一句
2. 括号内的舞台描述和括号外的对话算同一句，不要拆开，如"（轻声）你来了"是一句
3. 省略号"..."或"…"结尾的视作完整句子
4. 引号内的对话不要拆分
5. 直接输出 JSON 字符串数组，不要任何其他内容

文本：
{text}

输出示例：["句子一","句子二","句子三"]"""

    from core.llm_client import call_llm
    try:
        result = await asyncio.to_thread(
            call_llm, prompt=prompt, temperature=0, max_tokens=500, timeout=15, json_mode=True
        )
        if result and isinstance(result, list) and len(result) > 0:
            return {"sentences": [s.strip() for s in result if s.strip()]}
    except Exception as e:
        logger.warning(f"[分句API] 失败: {e}")

    return {"sentences": fallback_split(text)}


def fallback_split(text: str) -> list:
    """DFA 状态机分句 —— 处理角色扮演括号动作 + 对话 + 普通文本"""
    import re

    S_NORMAL = 0      # 普通叙述/对话
    S_IN_PAREN = 1    # 在（...）括号内
    S_AFTER_PAREN = 2 # 刚出括号，等待后续对话

    MAX_LEN = 80  # 超长无界句子在 ，处截断

    sentences = []
    buf = ''       # 当前累积的句子
    paren_buf = '' # 括号内动作内容（含括号）
    state = S_NORMAL

    i = 0
    n = len(text)

    def flush(force=False):
        nonlocal buf, paren_buf
        s = buf.strip()
        if len(s) >= 2:
            # 超长无结束符 → 在 ，处拆分
            if not re.search(r'[。！？!?…～]$', s) and len(s) > MAX_LEN:
                sub = re.split(r'(?<=[，,])', s)
                for p in sub:
                    p = p.strip()
                    if len(p) >= 2:
                        sentences.append(p)
            else:
                sentences.append(s)
        buf = ''

    def is_sentence_end(ch):
        return ch in '。！？!?…～~'

    while i < n:
        ch = text[i]

        if state == S_NORMAL:
            if i < n and text[i:i+1] == '（':
                # 进入括号前，先刷出已累积的叙述
                if buf.strip():
                    flush()
                state = S_IN_PAREN
                paren_buf = '（'
                i += 1
                continue
            elif ch == '\n' and i+1 < n and text[i+1] == '\n':
                # 双换行：段落分隔
                if buf.strip():
                    flush()
                i += 2
                continue
            else:
                buf += ch
                if is_sentence_end(ch):
                    flush()
        elif state == S_IN_PAREN:
            paren_buf += ch
            if ch == '）':
                state = S_AFTER_PAREN
                # 检查括号后是否紧接换行（无对话跟随）
                if i+1 < n and text[i+1] == '\n':
                    # 括号独段 → 括号内容独立出句
                    if len(paren_buf.strip()) >= 2:
                        sentences.append(paren_buf.strip())
                    paren_buf = ''
                    state = S_NORMAL
        elif state == S_AFTER_PAREN:
            if i < n and text[i:i+1] == '（':
                # 括号后直接遇到新括号 → 当前括号无对话跟随，独立出句
                if len(paren_buf.strip()) >= 2:
                    sentences.append(paren_buf.strip())
                paren_buf = ''
                state = S_IN_PAREN
                paren_buf = '（'
                i += 1
                continue
            elif ch == '\n' and i+1 < n and text[i+1] == '\n':
                # 括号后双换行 → 括号无对话跟随
                if len(paren_buf.strip()) >= 2:
                    sentences.append(paren_buf.strip())
                paren_buf = ''
                if buf.strip():
                    flush()
                state = S_NORMAL
                i += 2
                continue
            elif ch == '\n':
                # 单换行在AFTER_PAREN状态中当作段落分隔
                if len(paren_buf.strip()) >= 2:
                    sentences.append(paren_buf.strip())
                paren_buf = ''
                state = S_NORMAL
                i += 1
                continue
            else:
                paren_buf += ch
                if is_sentence_end(ch):
                    # 括号动作 + 后续对话 = 一句
                    s = paren_buf.strip()
                    if len(s) >= 2:
                        sentences.append(s)
                    paren_buf = ''
                    state = S_NORMAL
        i += 1

    # 处理残留
    if paren_buf.strip() and len(paren_buf.strip()) >= 2:
        sentences.append(paren_buf.strip())
    if buf.strip() and len(buf.strip()) >= 2:
        s = buf.strip()
        if not re.search(r'[。！？!?…～]$', s) and len(s) > MAX_LEN:
            import re as _re
            sub = _re.split(r'(?<=[，,])', s)
            for p in sub:
                p = p.strip()
                if len(p) >= 2:
                    sentences.append(p)
        else:
            sentences.append(s)

    return sentences


def split_next(text: str) -> tuple:
    """从文本开头提取下一个完整句子，返回 (sentence, remaining_text)
    用于前端流式分句 —— DFA 状态机从前向后扫描，遇到句子边界时停止"""

    S_NORMAL = 0
    S_IN_PAREN = 1
    S_AFTER_PAREN = 2

    MAX_LEN = 80
    buf = ''
    paren_buf = ''
    state = S_NORMAL

    def greedy_end(text, pos):
        """贪婪消费连续的同类型句子结束符（如 …… 或 ～～）"""
        end_chars = '。！？!?…～'
        j = pos + 1
        while j < len(text) and text[j] in end_chars and text[j] not in '。！？!?':
            j += 1
        return j

    i = 0
    n = len(text)

    while i < n:
        ch = text[i]

        if state == S_NORMAL:
            if i < n and text[i:i+1] == '（':
                if buf.strip():
                    return buf.strip(), text[i:]
                state = S_IN_PAREN
                paren_buf = '（'
                i += 1
                continue
            elif ch == '\n' and i+1 < n and text[i+1] == '\n':
                if buf.strip():
                    return buf.strip(), text[i+2:]
                i += 2
                continue
            else:
                buf += ch
                if ch in '。！？!?…～':
                    end = greedy_end(text, i)
                    buf += text[i+1:end]
                    i = end
                    return buf.strip(), text[i:]
        elif state == S_IN_PAREN:
            paren_buf += ch
            if ch == '）':
                state = S_AFTER_PAREN
                if i+1 < n and text[i+1] == '\n':
                    s = paren_buf.strip()
                    if len(s) >= 2:
                        return s, text[i+1:]
                    paren_buf = ''
                    state = S_NORMAL
        elif state == S_AFTER_PAREN:
            if i < n and text[i:i+1] == '（':
                s = paren_buf.strip()
                if len(s) >= 2:
                    return s, text[i:]
                paren_buf = '（'
                state = S_IN_PAREN
                i += 1
                continue
            elif ch == '\n' and i+1 < n and text[i+1] == '\n':
                s = paren_buf.strip()
                if len(s) >= 2:
                    return s, text[i+2:]
                paren_buf = ''
                state = S_NORMAL
                i += 2
                continue
            elif ch == '\n':
                s = paren_buf.strip()
                if len(s) >= 2:
                    return s, text[i+1:]
                paren_buf = ''
                state = S_NORMAL
                i += 1
                continue
            else:
                paren_buf += ch
                if ch in '。！？!?…～':
                    end = greedy_end(text, i)
                    paren_buf += text[i+1:end]
                    i = end
                    s = paren_buf.strip()
                    if len(s) >= 2:
                        return s, text[i:]
        i += 1

    return text.strip(), ''
