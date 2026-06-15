# core/vector_store/search.py — 搜索相关：向量检索 + MMR + 混合排序
import math
import logging
from datetime import datetime
from core.retry import silent_exc
from .model import is_model_ready, get_embedding_model, get_collection
from . import bm25 as _bm25_mod
from .bm25 import _get_bm25, _tokenize, _update_access_batch, _keyword_search_memories

logger = logging.getLogger(__name__)


def _check_duplicate(collection, embedding, sentence, threshold=0.85):
    """检查是否有相似记忆，返回 (is_dup, existing_id, existing_doc)"""
    try:
        results = collection.query(
            query_embeddings=[embedding],
            n_results=1,
            include=["documents", "distances"]
        )
        if results and results['documents'] and results['documents'][0]:
            doc = results['documents'][0][0]
            dist = results['distances'][0][0]
            cos_score = 1.0 - dist  # ChromaDB cosine space: dist = 1 - cos_sim
            if cos_score >= threshold:
                # 找到重复，获取ID
                existing_id = results['ids'][0][0] if results.get('ids') else None
                return True, existing_id, doc
    except Exception as e:
        silent_exc("_check_duplicate", e)
    return False, None, None


def _mmr_select(query_emb: list, candidates_with_emb: list, top_k: int, lambda_mult: float = 0.7) -> list:
    """MMR (Maximal Marginal Relevance) 多样性选择。
    确保返回结果既相关又多样，避免返回 5 条都是同一话题的记忆。

    Args:
        query_emb: 查询向量
        candidates_with_emb: [(doc, dist, meta, hybrid_score, embedding), ...]
        top_k: 返回数量
        lambda_mult: 0.0=最大多样性, 1.0=最大相关性 (默认 0.7 平衡)
    """
    if len(candidates_with_emb) <= top_k:
        return candidates_with_emb

    import numpy as np
    query_vec = np.array(query_emb)

    # 预计算所有候选与查询的余弦相似度
    def cosine_sim(a, b):
        a, b = np.array(a), np.array(b)
        norm = np.linalg.norm(a) * np.linalg.norm(b)
        return float(np.dot(a, b) / norm) if norm > 0 else 0.0

    selected = []
    remaining = list(range(len(candidates_with_emb)))

    for _ in range(top_k):
        if not remaining:
            break
        best_idx = -1
        best_score = -float('inf')
        for idx in remaining:
            _, _, _, hybrid, emb = candidates_with_emb[idx]
            # 与查询的相似度（用 hybrid_score 代替原始余弦）
            relevance = hybrid
            # 与已选结果的最大相似度
            max_sim = 0.0
            if selected and emb:
                for sel_idx in selected:
                    sel_emb = candidates_with_emb[sel_idx][4]
                    if sel_emb:
                        sim = cosine_sim(emb, sel_emb)
                        max_sim = max(max_sim, sim)
            # MMR 分数
            mmr_score = lambda_mult * relevance - (1 - lambda_mult) * max_sim
            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = idx
        if best_idx >= 0:
            selected.append(best_idx)
            remaining.remove(best_idx)

    return [candidates_with_emb[i] for i in selected]


def search_similar(query: str, top_k: int = 3, include_metadata: bool = False):
    """混合检索：优先 sentence_index，降级 chat_memory"""
    from .bm25 import reset_bm25_cache
    if not is_model_ready():
        return []
    try:
        model = get_embedding_model()
        query_emb = model.encode(query).tolist()
        # 优先从句子索引检索
        _search_collection = "sentence_index"
        collection = get_collection("sentence_index")
        if collection.count() == 0:
            collection = get_collection()  # 降级到旧的 chat_memory
            _search_collection = None
            reset_bm25_cache()  # 切换 collection，重置 BM25 缓存
        # 向量检索取 top_k * 3，再用 BM25 重排序 + MMR 多样性
        results = collection.query(
            query_embeddings=[query_emb],
            n_results=min(top_k * 3, 20),
            include=["documents", "distances", "metadatas", "embeddings"]
        )
        if not results or not results['documents'] or not results['documents'][0]:
            return []

        docs = results['documents'][0]
        distances = results['distances'][0] if results['distances'] else []
        metadatas = results['metadatas'][0] if results.get('metadatas') else [{}] * len(docs)
        embeddings = results['embeddings'][0] if results.get('embeddings') else [None] * len(docs)
        candidates = list(zip(docs, distances, metadatas, embeddings))

        # 三因子混合排序（相似度 + BM25 + 时效性 + 重要性）
        from core.db import get_all_memory_importance
        now = datetime.now()
        importance_map = get_all_memory_importance()

        bm25 = _get_bm25(_search_collection)
        if bm25:
            tokenized_query = _tokenize(query)
            bm25_scores = bm25.get_scores(tokenized_query)
            bm25_max = max(bm25_scores) if len(bm25_scores) > 0 and max(bm25_scores) > 0 else 1
            scored = []
            for doc, dist, meta, emb in candidates:
                cos_score = 1.0 - dist  # ChromaDB cosine space: dist = 1 - cos_sim
                try:
                    idx = _bm25_mod._bm25_docs.index(doc) if _bm25_mod._bm25_docs else -1
                    bm25_norm = (bm25_scores[idx] / bm25_max) if idx >= 0 and idx < len(bm25_scores) else 0
                except (ValueError, IndexError):
                    bm25_norm = 0

                # 时效性分数（指数衰减）
                recency_score = 1.0
                if meta and meta.get("msg_id"):
                    sid = f"s_{meta['msg_id']}_{meta.get('seq', 0)}"
                    imp_info = importance_map.get(sid, {})
                    created_at = imp_info.get("created_at")
                    if created_at:
                        try:
                            created = datetime.fromisoformat(created_at)
                            hours_since = (now - created).total_seconds() / 3600
                            recency_score = math.exp(-0.001 * hours_since)
                        except Exception:
                            recency_score = 1.0

                # 重要性分数
                importance_score = 0.5  # 默认
                if meta and meta.get("msg_id"):
                    sid = f"s_{meta['msg_id']}_{meta.get('seq', 0)}"
                    imp_info = importance_map.get(sid, {})
                    importance_score = imp_info.get("importance", 5.0) / 10.0

                # 最终分数：0.5×相似度 + 0.2×BM25 + 0.2×时效性 + 0.1×重要性
                hybrid = 0.5 * cos_score + 0.2 * bm25_norm + 0.2 * recency_score + 0.1 * importance_score
                scored.append((doc, dist, meta, hybrid, emb))

            scored.sort(key=lambda x: -x[3])
            # MMR 多样性选择（Zep 方案）：避免返回重复话题的记忆
            mmr_result = _mmr_select(query_emb, scored, top_k, lambda_mult=0.7)
            # 只更新 MMR 最终选中的结果的访问记录
            _update_access_batch(mmr_result)
            if include_metadata:
                return [(doc, dist, meta) for doc, dist, meta, _, _ in mmr_result]
            return [(doc, dist) for doc, dist, _, _, _ in mmr_result]

        # 无 BM25 时的简单路径
        simple = [(doc, dist, meta, 1.0 - dist, emb) for doc, dist, meta, emb in candidates]  # ChromaDB cosine: dist = 1 - cos_sim
        simple.sort(key=lambda x: -x[3])
        mmr_result = _mmr_select(query_emb, simple, top_k, lambda_mult=0.7)
        _update_access_batch(mmr_result)
        if include_metadata:
            return [(doc, dist, meta) for doc, dist, meta, _, _ in mmr_result]
        return [(doc, dist) for doc, dist, _, _, _ in mmr_result]
    except Exception as e:
        print(f"[向量搜索] 查询失败: {e}")
        return []


def search_knowledge_similar(query, top_k=5):
    """搜索知识库向量"""
    if not is_model_ready():
        return []
    model = get_embedding_model()
    query_emb = model.encode(query).tolist()
    collection = get_collection("knowledge_base")
    try:
        results = collection.query(query_embeddings=[query_emb], n_results=top_k, include=["documents", "distances"])
        if results and results['documents'] and results['documents'][0]:
            return list(zip(results['documents'][0], results['distances'][0] if results['distances'] else []))
    except Exception as e:
        print(f"[知识库检索] 异常: {e}")
    return []


def search_memories(query: str, top_k: int = 5) -> list[dict]:
    """向量检索记忆库（memory_store collection），返回 [{"key", "value", "score"}, ...]。
    若向量模型未就绪或库为空，降级为关键词检索。
    """
    if not is_model_ready():
        return _keyword_search_memories(query, top_k)

    try:
        model = get_embedding_model()
        query_emb = model.encode(query).tolist()
        collection = get_collection("memory_store")

        # 检查 collection 是否为空
        count = collection.count()
        if count == 0:
            return _keyword_search_memories(query, top_k)

        results = collection.query(
            query_embeddings=[query_emb],
            n_results=top_k,
            include=["documents", "distances", "metadatas"]
        )
        if not results or not results.get("documents") or not results["documents"][0]:
            return _keyword_search_memories(query, top_k)

        items = []
        for doc, dist, meta in zip(
            results["documents"][0],
            results["distances"][0] if results.get("distances") else [],
            results["metadatas"][0] if results.get("metadatas") else [{}] * top_k
        ):
            cos_score = 1.0 - dist if dist <= 2.0 else 0.5
            items.append({
                "key": (meta or {}).get("key", ""),
                "value": doc,
                "score": round(cos_score, 4),
                "type": (meta or {}).get("type", "memory"),
            })
        return items
    except Exception as e:
        print(f"[记忆向量] 检索失败: {e}")
        return _keyword_search_memories(query, top_k)