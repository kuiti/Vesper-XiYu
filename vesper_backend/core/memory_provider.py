# core/memory_provider.py — 统一记忆提供者
"""封装所有"AI 对用户的了解"的存储和查询。

设计目标：
1. MemoryProvider 是统一入口，替换散在 pipeline/search/consolidation 中直接操作
   user_profile/facts 的代码
2. 下游不需要知道存储后端（目前是 SQLite user_profile，未来可换）
3. 支持 category 分类（FACT/EMOTION/PREFERENCE/EVENT/HABIT/RELATIONSHIP）

使用方法：
    provider = MemoryProvider()
    ctx = provider.get_context(character_id=0, query="用户喜欢什么")
    provider.save_fact(character_id=0, content="用户喜欢面条", category="PREFERENCE")
"""

import json
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional
from core.retry import silent_exc

logger = logging.getLogger(__name__)

# 记忆分类
MEMORY_CATEGORIES = ("FACT", "EMOTION", "PREFERENCE", "EVENT", "HABIT", "RELATIONSHIP")


class MemoryProvider:
    """统一记忆提供者（per-character，线程安全）"""

    def get_context(self, character_id: int = 0, query: str = "", limit: int = 5) -> str:
        """获取格式化记忆上下文用于 prompt 注入。

        Returns:
            格式化字符串：多条记忆，按重要性排序。无记忆时返回空字符串。
        """
        from core.db import get_chat_conn
        try:
            with get_chat_conn(character_id) as conn:
                cursor = conn.cursor()
                # 读取 user_profile（核心事实）
                cursor.execute(
                    "SELECT key, value, confidence FROM user_profile "
                    "WHERE key NOT LIKE '_%' ORDER BY confidence DESC LIMIT ?",
                    (limit,)
                )
                facts = cursor.fetchall()
                # 读取带标签的事实
                cursor.execute(
                    "SELECT key, value, confidence FROM user_profile "
                    "WHERE key LIKE '_fact_%' AND confidence >= 0.7 "
                    "ORDER BY confidence DESC LIMIT ?",
                    (limit,)
                )
                more_facts = cursor.fetchall()
        except Exception as e:
            silent_exc("MemoryProvider.get_context", e)
            return ""

        lines = []
        for r in facts + more_facts:
            key = r["key"].lstrip("_").replace("_fact_", "").replace("_", " ")
            val = r["value"]
            conf = r["confidence"]
            if len(val) > 200:
                val = val[:200] + "…"
            lines.append(f"- {key}: {val}（置信度{conf:.0%}）")

        if not lines:
            return ""
        return "【关于对方的了解】\n" + "\n".join(lines)

    def save_fact(self, character_id: int, content: str, category: str = "FACT",
                  confidence: float = 1.0, source: str = ""):
        """保存一条事实/偏好/事件到 user_profile。

        Args:
            character_id: 角色 ID
            content: 事实文本
            category: MEMORY_CATEGORIES 之一
            confidence: 置信度 0-1
            source: 来源（"conversation" / "import" / "mcp" 等）
        """
        if not content or not content.strip():
            return
        from core.db import get_chat_conn
        import hashlib
        fact_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        key = f"_fact_{fact_hash}"
        now = datetime.now().isoformat()
        # 内容也存，方便搜索
        value = json.dumps({"text": content.strip(), "category": category, "source": source},
                           ensure_ascii=False)
        try:
            with get_chat_conn(character_id) as conn:
                conn.cursor().execute(
                    "INSERT OR REPLACE INTO user_profile (key, value, confidence, extracted_at) VALUES (?, ?, ?, ?)",
                    (key, value, float(confidence), now)
                )
            logger.debug(f"[记忆] 保存事实: [{category}] {content[:50]} (角色{character_id})")
        except Exception as e:
            silent_exc("MemoryProvider.save_fact", e)

    def search_facts(self, character_id: int = 0, query: str = "", limit: int = 10) -> list:
        """搜索用户事实（关键词匹配 value）。"""
        if not query:
            return []
        from core.db import get_chat_conn
        try:
            with get_chat_conn(character_id) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT key, value, confidence, extracted_at FROM user_profile "
                    "WHERE value LIKE ? ORDER BY confidence DESC LIMIT ?",
                    (f"%{query}%", limit)
                )
                results = []
                for r in cursor.fetchall():
                    try:
                        parsed = json.loads(r["value"])
                        text = parsed.get("text", r["value"])
                        cat = parsed.get("category", "FACT")
                    except (json.JSONDecodeError, TypeError):
                        text = r["value"]
                        cat = "FACT"
                    results.append({
                        "content": text,
                        "category": cat,
                        "confidence": r["confidence"],
                        "extracted_at": r["extracted_at"],
                    })
                return results
        except Exception as e:
            silent_exc("MemoryProvider.search_facts", e)
            return []

    def get_stats(self, character_id: int = 0) -> dict:
        """获取该角色的记忆统计。"""
        from core.db import get_chat_conn
        try:
            with get_chat_conn(character_id) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as n FROM user_profile")
                total = cursor.fetchone()["n"]
                cursor.execute("SELECT COUNT(*) as n FROM user_profile WHERE confidence >= 0.8")
                high_conf = cursor.fetchone()["n"]
                return {"total_entries": total, "high_confidence": high_conf}
        except Exception as e:
            silent_exc("MemoryProvider.get_stats", e)
            return {"total_entries": 0, "high_confidence": 0}

    def extract_entities_from_text(self, text: str, character_id: int = 0, max_entities: int = 5):
        """从文本中提取实体（人名/地点/事物），写入 entities 表。
        轻量实现：jieba 词性标注 + 停用词过滤，不调 LLM。
        """
        if not text or len(text) < 5:
            return
        try:
            import jieba.posseg as pseg
            from core.db import get_chat_conn
            now = datetime.now().isoformat()
            stop = {"的", "了", "是", "我", "你", "他", "她", "它", "在",
                    "有", "和", "就", "也", "不", "都", "这", "那", "什么"}
            entities = []
            for w, flag in pseg.cut(text):
                w = w.strip()
                if len(w) < 2 or len(w) > 10 or w in stop:
                    continue
                if flag.startswith('n') or flag.startswith('v'):
                    entities.append(w)
            if not entities:
                return
            seen = set()
            uniq = []
            for e in entities:
                if e not in seen:
                    seen.add(e)
                    uniq.append(e)
            from core.db import get_chat_conn
            with get_chat_conn(character_id) as conn:
                cursor = conn.cursor()
                import hashlib
                for e in uniq[:max_entities]:
                    e_hash = hashlib.md5(e.encode()).hexdigest()[:8]
                    cursor.execute(
                        "INSERT OR IGNORE INTO entities (entity_text, entity_type, entity_hash, created_at) VALUES (?, ?, ?, ?)",
                        (e, "phrase", e_hash, now)
                    )
        except Exception as e:
            silent_exc("MemoryProvider.extract_entities", e)

    def extract_vocabulary_from_text(self, text: str, character_id: int = 0, max_items: int = 3):
        """从文本中提取用户特有词汇/用语，写入 user_vocabulary 表。
        轻量实现：找 jieba 切出的非常用词。
        """
        if not text or len(text) < 3:
            return
        try:
            import jieba
            from core.db import get_chat_conn
            from collections import Counter
            now = datetime.now().isoformat()
            stop = {"的", "了", "是", "我", "你", "他", "她", "它", "在",
                    "有", "和", "就", "也", "不", "都", "这", "那", "什么",
                    "可以", "知道", "觉得", "感觉", "现在", "今天", "昨天",
                    "明天", "一下", "还是", "已经", "没有", "一个", "吗",
                    "啊", "哦", "嗯", "吧", "呢", "呀", "哈", "嘿"}
            words = []
            for w in jieba.cut(text):
                w = w.strip()
                if len(w) >= 2 and len(w) <= 8 and w not in stop and not w.isdigit():
                    words.append(w)
            if not words:
                return
            freq = Counter(words)
            with get_chat_conn(character_id) as conn:
                cursor = conn.cursor()
                for word, cnt in freq.most_common(max_items):
                    cursor.execute("SELECT id, use_count FROM user_vocabulary WHERE phrase = ?", (word,))
                    existing = cursor.fetchone()
                    if existing:
                        cursor.execute(
                            "UPDATE user_vocabulary SET use_count = use_count + ?, last_used = ? WHERE id = ?",
                            (cnt, now, existing["id"])
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO user_vocabulary (phrase, meaning, use_count, last_used, created_at) VALUES (?, '', ?, ?, ?)",
                            (word, cnt, now, now)
                        )
        except Exception as e:
            silent_exc("MemoryProvider.extract_vocabulary", e)


# ─── TempMemory 管道 ───

def save_temp_conversation(character_id: int, user_msg: str, ai_reply: str):
    """暂存一轮对话到 temp_memory，供后续批量巩固使用。

    TempMemory 桥接短期→长期记忆：
    1. 每次对话写入 temp_memory（user_msg + ai_reply）
    2. 每 N 条或每日运行 batch_extract_memories
    3. 提取的事实写入 user_profile，temp 记录标记为已处理
    """
    if not user_msg or not ai_reply:
        return
    from core.db import get_chat_conn
    from core.db import get_config
    now = datetime.now().isoformat()
    try:
        with get_chat_conn(character_id) as conn:
            conn.cursor().execute(
                "INSERT INTO temp_memory (character_id, user_input, ai_response, created_at) VALUES (?, ?, ?, ?)",
                (character_id, user_msg[:500], ai_reply[:500], now)
            )
    except Exception as e:
        silent_exc("save_temp_conversation", e)


# per-character 锁，防止 batch_extract 并发处理同一批记录
_batch_locks: dict[int, threading.Lock] = {}
_batch_locks_lock = threading.Lock()


def _get_batch_lock(character_id: int) -> threading.Lock:
    with _batch_locks_lock:
        if character_id not in _batch_locks:
            _batch_locks[character_id] = threading.Lock()
        return _batch_locks[character_id]


def batch_extract_memories(character_id: int = 0, max_items: int = 10):
    """批量提取未处理的 TempMemory 为正式记忆。

    从 temp_memory 读取未处理的记录，调用 LLM 提取事实/偏好/事件，
    写入 user_profile，标记 temp 记录为已处理。
    """
    lock = _get_batch_lock(character_id)
    if not lock.acquire(blocking=False):
        return 0  # 已有线程在处理同一角色的批量提取，跳过
    try:
        from core.db import get_chat_conn
        with get_chat_conn(character_id) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, user_input, ai_response FROM temp_memory WHERE processed = 0 ORDER BY id ASC LIMIT ?",
                (max_items,)
            )
            rows = cursor.fetchall()
            if not rows:
                return 0

            # 合并上下文
            combined = ""
            for r in rows:
                combined += f"用户: {r['user_input']}\nAI: {r['ai_response']}\n"

            # 尝试调用 LLM 提取事实
            facts = _llm_extract_facts(combined)
            saved = 0
            if facts:
                provider = MemoryProvider()
                for f in facts:
                    provider.save_fact(
                        character_id=character_id,
                        content=f.get("text", ""),
                        category=f.get("category", "FACT"),
                        confidence=f.get("confidence", 0.7),
                        source="conversation"
                    )
                    saved += 1

            # 标记已处理
            ids = [str(r["id"]) for r in rows]
            cursor.execute(
                f"UPDATE temp_memory SET processed = 1 WHERE id IN ({','.join('?' * len(ids))})",
                ids
            )
            conn.commit()
            if saved:
                logger.info(f"[记忆] 批量巩固: 角色{character_id} {saved}/{len(rows)} 条")
            return saved
    except Exception as e:
        silent_exc("batch_extract_memories", e)
        return 0
    finally:
        lock.release()


def _llm_extract_facts(text: str) -> list:
    """用 LLM 从对话中提取事实性信息。

    Returns:
        [{"text": "...", "category": "FACT|PREFERENCE|EVENT", "confidence": 0.8}, ...]
    """
    from core.llm_client import call_llm
    prompt = (
        "从以下对话中提取关于用户的事实性信息（偏好、习惯、事件、关系等）。\n"
        "只提取明确说出的内容，不要推测。按 JSON 格式返回列表。\n"
        "每条格式：{\"text\": \"事实描述\", \"category\": \"FACT|PREFERENCE|EVENT|HABIT\", \"confidence\": 0~1}\n"
        "如果无任何可提取信息，返回 []。\n\n"
        f"对话：\n{text[:2000]}"
    )
    try:
        result = call_llm(prompt, temperature=0.1, max_tokens=500, json_mode=True)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return result.get("facts", result.get("conclusions", []))
        return []
    except Exception as e:
        silent_exc("_llm_extract_facts", e)
        return []
