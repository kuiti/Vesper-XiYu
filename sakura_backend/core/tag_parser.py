"""
Tag 指令解析器 —— AI 回复中的 <add:> <search:> 等标签解析和执行
作为 function calling 的 fallback：当 AI 忘了调工具但输出了标签时，后端代为执行
"""

import re
import json
from datetime import datetime
from typing import Optional
import logging
from core.retry import silent_exc
logger = logging.getLogger(__name__)


class TagParser:
    """解析 AI 回复中的标签指令"""

    PATTERNS = {
        "add":       re.compile(r"<add:(.+?)>"),
        "search":    re.compile(r"<search:(.+?)>"),
        "note":      re.compile(r"<note:(.+?)>"),
        "todo":      re.compile(r"<todo:(.+?)>"),
        "proactive": re.compile(r"<proactive:(.+?)>"),
    }

    @staticmethod
    def parse(text: str) -> list[dict]:
        """解析文本中的所有标签，返回 [{"type": "add", "content": "..."}, ...]"""
        results = []
        for tag_type, pattern in TagParser.PATTERNS.items():
            for match in pattern.finditer(text):
                results.append({
                    "type": tag_type,
                    "content": match.group(1).strip(),
                })
        return results

    @staticmethod
    def strip_tags(text: str) -> str:
        """从文本中移除所有标签，只留纯文本"""
        result = text
        for pattern in TagParser.PATTERNS.values():
            result = pattern.sub("", result)
        result = re.sub(r"\n{3,}", "\n\n", result).strip()
        return result


class TagExecutor:
    """执行解析出的标签指令，返回可选的 system 反馈"""

    @staticmethod
    def execute(tag: dict) -> Optional[str]:
        """执行单个标签，返回 system 反馈消息（None = 无需反馈）"""
        t = tag["type"]
        content = tag["content"]
        if t == "add":
            return TagExecutor._add(content)
        elif t == "search":
            return TagExecutor._search(content)
        elif t == "note":
            return TagExecutor._note(content)
        elif t == "todo":
            return TagExecutor._todo(content)
        return None

    @staticmethod
    def execute_all(tags: list[dict]) -> list[dict]:
        """执行所有标签，返回每条的执行结果"""
        results = []
        for tag in tags:
            try:
                feedback = TagExecutor.execute(tag)
                results.append({**tag, "success": True, "feedback": feedback})
            except Exception as e:
                results.append({**tag, "success": False, "feedback": str(e)})
        return results

    @staticmethod
    def _add(content: str) -> str:
        """保存记忆 —— 对应 declare_memory_intent"""
        from core.db import get_conn, get_config
        import hashlib

        summary = content
        fact_hash = hashlib.md5(summary.encode()).hexdigest()
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM user_profile WHERE key = ?", (f"_fact_{fact_hash}",))
            if cursor.fetchone():
                return f"已记住啦：{content}"
            cursor.execute(
                "REPLACE INTO user_profile (key, value, confidence, extracted_at) VALUES (?, ?, ?, ?)",
                (f"_fact_{fact_hash}", json.dumps({
                    "text": summary,
                    "category": "memory",
                    "importance": 6,
                    "created_at": datetime.now().isoformat()
                }, ensure_ascii=False), 0.8, datetime.now().isoformat())
            )
        # 清除画像缓存
        try:
            from core.profile_builder import clear_profile_cache
            clear_profile_cache()
        except Exception as e:
            silent_exc("_add", e)
        return f"已记住：{content}"

    @staticmethod
    def _search(keyword: str) -> str:
        """搜索记忆 —— 对应 search_memory"""
        from core.db import get_conn
        # 转义 LIKE 通配符
        safe_kw = keyword.replace('%', '\\%').replace('_', '\\_')
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT value FROM user_profile WHERE key LIKE '_fact_%' AND value LIKE ? ESCAPE '\\' ORDER BY extracted_at DESC LIMIT 5",
                (f"%{safe_kw}%",)
            )
            rows = cursor.fetchall()
        if not rows:
            return f"没找到关于「{keyword}」的记忆"
        entries = []
        for r in rows:
            try:
                d = json.loads(r["value"])
                entries.append(f"📝 {d.get('text', '')}")
            except Exception:
                entries.append(f"📝 {r['value'][:80]}")
        return "在记忆库中找到了以下相关内容：\n" + "\n".join(entries)

    @staticmethod
    def _note(content: str) -> str:
        """存笔记 —— 对应 add_note"""
        from core.db import add_note
        title = content[:20] if len(content) > 20 else content
        add_note(title, content)
        return None  # 存笔记不需要反馈到对话

    @staticmethod
    def _todo(content: str) -> str:
        """加待办 —— 对应 add_todo"""
        from core.db import add_todo
        add_todo(content)
        return None


def parse_interval(text: str) -> Optional[int]:
    """解析时间间隔字符串（如 '30min'、'1h'、'5s'），返回秒数"""
    if not text:
        return None
    text = text.strip().lower()
    m = re.match(r"(\d+)\s*(s|秒|sec|min|分钟|m|h|小时|hour)", text)
    if not m:
        return None
    value = int(m.group(1))
    if value <= 0 or value > 86400:
        return None
    unit = m.group(2)
    if unit in ("s", "秒", "sec"):
        return value
    elif unit in ("min", "分钟", "m"):
        return value * 60
    elif unit in ("h", "小时", "hour"):
        return value * 3600
    return None


def process_reply_tags(ai_reply: str, tool_calls_used: bool = False) -> tuple:
    """
    处理 AI 回复中的标签。
    - 如果 function calling 已执行（tool_calls_used=True），跳过标签（避免重复）
    - 否则解析并执行标签
    - 返回 (cleaned_text, feedback_list)
      - cleaned_text: 移除了标签的文本（None=无标签）
      - feedback_list: 执行反馈消息列表
    """
    tags = TagParser.parse(ai_reply)
    if not tags:
        return None, []

    if tool_calls_used:
        return TagParser.strip_tags(ai_reply), []

    # 执行标签
    results = TagExecutor.execute_all(tags)
    print(f"[TagParser] 执行了 {len(results)} 个标签: {[r['type'] for r in results]}")

    # 收集非空反馈
    feedback_list = [r["feedback"] for r in results if r.get("feedback")]

    # 清理标签后的文本
    clean_text = TagParser.strip_tags(ai_reply)
    return clean_text, feedback_list
