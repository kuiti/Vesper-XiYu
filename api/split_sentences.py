"""
智能分句 —— 调用 DeepSeek API 识别句子边界  |  v3.8.0
对角色扮演/对话类文本中的省略号、括号、引号等复杂场景做准确切分
更新: 新增 API 端点 POST /text/split，fallback 本地正则
"""
# version: 3.8.0
from fastapi import APIRouter
from pydantic import BaseModel
from core.db import get_config
import requests
import json

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

    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0, "max_tokens": 500},
            timeout=15
        )
        resp.raise_for_status()
        result = resp.json()["choices"][0]["message"]["content"]
        result = result.strip()
        for prefix in ['```json', '```']:
            if result.startswith(prefix):
                result = result[len(prefix):].strip()
        for suffix in ['```']:
            if result.endswith(suffix):
                result = result[:-len(suffix)].strip()
        sentences = json.loads(result)
        if isinstance(sentences, list) and len(sentences) > 0:
            return {"sentences": [s.strip() for s in sentences if s.strip()]}
    except Exception as e:
        print(f"[分句API] 失败: {e}")

    return {"sentences": fallback_split(text)}


def fallback_split(text: str) -> list:
    """本地正则分句（API 失败时的后备方案）"""
    import re
    parts = re.split(r'(?<=[。！？；!?;])\s*|(?<=\.{3})\s*|(?<=…)\s*|(?<=～)\s*|(?<=——)\s*', text)
    return [p.strip() for p in parts if p.strip() and len(p.strip()) >= 2]
