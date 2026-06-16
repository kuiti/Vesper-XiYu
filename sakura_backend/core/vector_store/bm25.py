# core/vector_store/bm25.py — BM25 索引 + 关键词回退检索
from core.retry import silent_exc
from .model import get_collection

# ─── BM25 全局缓存 ───
_bm25 = None
_bm25_docs = None
_bm25_hash = None  # 文档列表哈希，用于快速判断是否需要重建


def reset_bm25_cache():
    """重置 BM25 缓存（重建向量或新消息写入后调用）"""
    global _bm25, _bm25_docs, _bm25_hash
    _bm25 = None
    _bm25_docs = None
    _bm25_hash = None


def _tokenize(text):
    """中文分词：优先用 jieba，回退空格分词"""
    try:
        import jieba
        return list(jieba.cut(text))
    except ImportError:
        return text.split()


def _get_bm25(collection_name: str = None):
    global _bm25, _bm25_docs, _bm25_hash
    try:
        col = get_collection(collection_name)
        data = col.get(include=["documents"])
        docs = data.get("documents", [])
        if not docs:
            return None
        # 使用哈希快速判断文档列表是否变化
        current_hash = hash(tuple(docs))
        if _bm25_hash == current_hash:
            return _bm25
        from rank_bm25 import BM25Okapi
        tokenized = [_tokenize(d) for d in docs]
        _bm25 = BM25Okapi(tokenized)
        _bm25_docs = docs
        _bm25_hash = current_hash
        return _bm25
    except Exception:
        return None


def _update_access_batch(results: list):
    """批量更新 MMR 最终选中结果的访问记录"""
    try:
        from core.db import update_memory_access
        for item in results:
            meta = item[2] if len(item) > 2 else None
            if meta and meta.get("msg_id"):
                sid = f"s_{meta['msg_id']}_{meta.get('seq', 0)}"
                update_memory_access(sid)
    except Exception as e:
        silent_exc("_update_access_batch", e)


def _keyword_search_memories(query: str, top_k: int = 5) -> list[dict]:
    """关键词回退：从 memory 表和 user_profile 中模糊搜索"""
    query_lower = query.lower()
    results = []

    # memory 表
    try:
        from core.db import get_conn
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM memory")
            for r in cursor.fetchall():
                key = r["key"]
                value = r["value"]
                if query_lower in key.lower() or query_lower in value.lower():
                    results.append({"key": key, "value": value, "score": 0.5, "type": "memory"})
    except Exception as e:
        silent_exc("_keyword_search_memories", e)

    # user_profile 表
    try:
        from core.db import get_conn
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM user_profile")
            for r in cursor.fetchall():
                key = r["key"]
                value = str(r.get("value", ""))
                if query_lower in key.lower() or query_lower in value.lower():
                    results.append({"key": key, "value": value, "score": 0.4, "type": "profile"})
    except Exception as e:
        silent_exc("keyword_search_memories", e)

    return results[:top_k]