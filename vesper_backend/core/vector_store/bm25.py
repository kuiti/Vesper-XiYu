# core/vector_store/bm25.py — BM25 索引 + 关键词回退检索
import threading
from datetime import datetime
from core.retry import silent_exc
from .model import get_collection

# BM25 全局缓存
_bm25 = None
_bm25_docs = None
_bm25_hash = None
_bm25_gen = 0       # 写入时递增，重建后匹配
_bm25_doc_to_idx = None  # {doc_text: index} 映射，避免 search.py O(N) 重建

_BM25_LOCK = threading.Lock()


def reset_bm25_cache():
    """重置 BM25 缓存（写入后调用，仅标记脏，延迟重建）"""
    global _bm25_gen
    with _BM25_LOCK:
        _bm25_gen += 1


def _tokenize(text):
    """中文分词：优先用 jieba，回退空格分词"""
    try:
        import jieba
        return list(jieba.cut(text))
    except ImportError:
        return text.split()


def get_bm25(collection_name: str = None):
    """获取 BM25 索引 + doc_to_idx 映射。仅在版本不匹配时全量重建。"""
    global _bm25, _bm25_docs, _bm25_hash, _bm25_gen, _bm25_doc_to_idx
    try:
        current_gen = _bm25_gen
        with _BM25_LOCK:
            if _bm25 is not None and _bm25_hash is not None and current_gen == _bm25_gen:
                return _bm25, _bm25_doc_to_idx, _bm25_docs

        col = get_collection(collection_name)
        data = col.get(include=["documents"])
        docs = data.get("documents", [])
        if not docs:
            return None, None, None

        from rank_bm25 import BM25Okapi
        tokenized = [_tokenize(d) for d in docs]
        new_bm25 = BM25Okapi(tokenized)
        new_hash = hash(tuple(docs))
        new_doc_to_idx = {d: i for i, d in enumerate(docs)}

        with _BM25_LOCK:
            if current_gen != _bm25_gen:
                return None, None, None
            _bm25 = new_bm25
            _bm25_docs = docs
            _bm25_hash = new_hash
            _bm25_doc_to_idx = new_doc_to_idx
        return new_bm25, new_doc_to_idx, docs
    except Exception:
        return None, None, None


def _update_access_batch(results: list):
    """批量更新 MMR 选中结果的访问记录（单条 SQL）"""
    try:
        sids = []
        for item in results:
            meta = item[2] if len(item) > 2 else None
            if meta and meta.get("msg_id"):
                sids.append(f"s_{meta.get('character_id', 0)}_{meta['msg_id']}_{meta.get('seq', 0)}")
        if sids:
            from core.db import get_conn, update_memory_access
            if len(sids) <= 3:
                for sid in sids:
                    update_memory_access(sid)
            else:
                now = datetime.now().isoformat()
                with get_conn() as conn:
                    cursor = conn.cursor()
                    cursor.executemany(
                        """INSERT OR REPLACE INTO memory_importance (id, access_count, last_accessed)
                           VALUES (?, COALESCE((SELECT access_count FROM memory_importance WHERE id = ?), 0) + 1, ?)""",
                        [(sid, sid, now) for sid in sids]
                    )
    except Exception as e:
        silent_exc("_update_access_batch", e)


def _keyword_search_memories(query: str, top_k: int = 5) -> list[dict]:
    """关键词回退：用 SQL LIKE 模糊搜索 memory 表和 user_profile 表"""
    results = []
    like_pattern = f"%{query}%"
    try:
        from core.db import get_conn
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT key, value FROM memory WHERE key LIKE ? OR value LIKE ? LIMIT ?",
                (like_pattern, like_pattern, top_k)
            )
            for r in cursor.fetchall():
                results.append({"key": r["key"], "value": r["value"], "score": 0.5, "type": "memory"})
            if len(results) < top_k:
                cursor.execute(
                    "SELECT key, value FROM user_profile WHERE key LIKE ? OR value LIKE ? LIMIT ?",
                    (like_pattern, like_pattern, top_k - len(results))
                )
                for r in cursor.fetchall():
                    val = str(r.get("value", ""))
                    results.append({"key": r["key"], "value": val, "score": 0.4, "type": "profile"})
    except Exception as e:
        silent_exc("_keyword_search_memories", e)
    return results[:top_k]
