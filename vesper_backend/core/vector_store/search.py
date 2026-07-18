# core/vector_store/search.py — 搜索相关：向量检索 + MMR + 混合排序
import math
import logging
from datetime import datetime
from core.retry import silent_exc
from .model import is_model_ready, get_embedding_model, get_collection
from .bm25 import get_bm25, _tokenize, _update_access_batch, _keyword_search_memories

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
    """MMR (Maximal Marginal Relevance) numpy 向量化选择。"""
    if len(candidates_with_emb) <= top_k:
        return candidates_with_emb

    import numpy as np
    query_vec = np.array(query_emb).reshape(1, -1)

    n = len(candidates_with_emb)
    hybrid_scores = np.array([c[3] for c in candidates_with_emb])
    all_embs = np.array([c[4] for c in candidates_with_emb])

    norms = np.linalg.norm(all_embs, axis=1, keepdims=True)
    norms[norms == 0] = 1
    all_embs_norm = all_embs / norms

    selected = []
    remaining = list(range(n))

    for _ in range(min(top_k, n)):
        if not remaining:
            break
        rem_idx = np.array(remaining)
        rem_embs = all_embs_norm[rem_idx]
        rel = hybrid_scores[rem_idx]

        if selected:
            sel_embs = all_embs_norm[np.array(selected)]
            sim_matrix = np.dot(rem_embs, sel_embs.T)
            max_sim = np.max(sim_matrix, axis=1)
        else:
            max_sim = np.zeros(len(rem_idx))

        mmr = lambda_mult * rel - (1 - lambda_mult) * max_sim
        best_pos = int(np.argmax(mmr))
        best_global = remaining[best_pos]
        selected.append(best_global)
        remaining.pop(best_pos)

    return [candidates_with_emb[i] for i in selected]


def _semantic_dedup(mmr_result: list, cos_threshold: float = 0.92) -> list:
    """语义去重：cos_sim > 阈值的结果只保留 hybrid 分高的那条。
    MMR 已做了 diversity 选择，但同事件不同表述仍可能漏过，这是最后一道兜底。"""
    if len(mmr_result) <= 1:
        return mmr_result
    try:
        import numpy as np
        embs = [r[4] for r in mmr_result if r[4] is not None]
        if len(embs) < len(mmr_result):
            # 有候选缺 embedding，跳过去重避免误删
            return mmr_result
        embs_arr = np.array(embs)
        norms = np.linalg.norm(embs_arr, axis=1, keepdims=True)
        norms[norms == 0] = 1
        embs_norm = embs_arr / norms
        sim = np.dot(embs_norm, embs_norm.T)

        kept_idx = [0]
        for i in range(1, len(mmr_result)):
            max_sim_to_kept = max(sim[i, j] for j in kept_idx)
            if max_sim_to_kept < cos_threshold:
                kept_idx.append(i)
        return [mmr_result[i] for i in kept_idx]
    except Exception as e:
        silent_exc("_semantic_dedup", e)
        return mmr_result


def _candidate_count(top_k: int, query: str) -> int:
    """按查询长度动态决定候选数：短查询降噪，长查询提召回"""
    qlen = len(query) if query else 0
    if qlen < 8:
        mult = 2
    elif qlen <= 30:
        mult = 3
    else:
        mult = 4
    return min(top_k * mult, 30)


def _recency_score(hours_since: float) -> float:
    """分段时效性：7 天内满分，之后指数衰减（半衰期 ~6 天）。
    3 年使用场景下旧记忆不会彻底归零，但近期对话有明显加权。"""
    if hours_since <= 168:
        return 1.0
    return math.exp(-0.005 * (hours_since - 168))


def search_similar(query: str, top_k: int = 3, include_metadata: bool = False, character_id: int = 0):
    """混合检索：优先 sentence_index，降级 chat_memory
    character_id 用于 mention_weights 查询（per-character 隔离）
    """
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
        # 向量检索候选数按查询长度自适应（短查询降噪、长查询提召回）
        n_candidates = _candidate_count(top_k, query)
        # 按角色隔离过滤：character_id>0 时只搜该角色的句子
        _where = {"character_id": character_id} if character_id else None
        results = collection.query(
            query_embeddings=[query_emb],
            n_results=n_candidates,
            where=_where,
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
        from core.db import get_conn
        now = datetime.now()
        # 只查候选 id 的重要性（替代全表加载）
        candidate_sids = []
        for _, _, meta, _ in candidates:
            if meta and meta.get("msg_id"):
                candidate_sids.append(f"s_{meta.get('character_id', 0)}_{meta['msg_id']}_{meta.get('seq', 0)}")
        importance_map = {}
        if candidate_sids:
            try:
                with get_conn() as conn:
                    cursor = conn.cursor()
                    placeholders = ",".join("?" * len(candidate_sids))
                    cursor.execute(
                        f"SELECT id, importance, created_at, access_count, ignored_count FROM memory_importance WHERE id IN ({placeholders})",
                        candidate_sids
                    )
                    for r in cursor.fetchall():
                        importance_map[r["id"]] = {"importance": r["importance"], "created_at": r["created_at"], "access_count": r["access_count"] or 0, "ignored_count": r["ignored_count"] or 0}
            except Exception as e:
                logger.warning(f"[搜索] 重要性查询失败: {e}")

        bm25, bm25_doc_to_idx, _ = get_bm25(_search_collection)
        if bm25:
            tokenized_query = _tokenize(query)
            bm25_scores = bm25.get_scores(tokenized_query)
            bm25_max = max(bm25_scores) if len(bm25_scores) > 0 and max(bm25_scores) > 0 else 1

            # 第5信号：实体匹配（预计算查询实体）
            query_entities = set()
            try:
                from core.profile_builder import extract_entities_from_text
                query_entities = set(e[0] for e in extract_entities_from_text(query))
            except Exception as e:
                logger.warning(f"[搜索] 实体提取失败: {e}")

            # 第7信号：提及权重（用户反复说过的事优先）
            # 收集所有候选 doc 的关键短语，一次性查 mention_weights
            mention_weights_map = {}
            try:
                from core.mention_tracker import get_mention_weights
                all_phrases = set()
                for doc, _, _, _ in candidates:
                    # 用 jieba 提取（与 mention_tracker 一致）
                    try:
                        import jieba
                        for w in jieba.cut(doc):
                            if len(w) >= 2 and len(w) <= 8 and not w.isdigit():
                                all_phrases.add(w)
                    except Exception:
                        pass
                if all_phrases:
                    mention_weights_map = get_mention_weights(list(all_phrases), character_id=character_id)
            except Exception as e:
                logger.debug(f"[搜索] 提及权重查询失败: {e}")

            scored = []
            for doc, dist, meta, emb in candidates:
                cos_score = 1.0 - dist
                idx = bm25_doc_to_idx.get(doc, -1) if bm25_doc_to_idx else -1
                bm25_norm = (bm25_scores[idx] / bm25_max) if idx >= 0 and idx < len(bm25_scores) else 0

                # 时效性分数（分段：7 天内满分，之后指数衰减）
                recency_score = 1.0
                if meta and meta.get("msg_id"):
                    sid = f"s_{meta.get('character_id', 0)}_{meta['msg_id']}_{meta.get('seq', 0)}"
                    imp_info = importance_map.get(sid, {})
                    created_at = imp_info.get("created_at")
                    if created_at:
                        try:
                            created = datetime.fromisoformat(created_at)
                            hours_since = max(0, (now - created).total_seconds() / 3600)
                            recency_score = _recency_score(hours_since)
                        except Exception:
                            recency_score = 1.0

                # 重要性分数：归一化 (imp-1)/9，让默认 5.0 → 0.44，9.0 → 0.89
                importance_score = 0.44  # 默认 5.0 的归一化值
                if meta and meta.get("msg_id"):
                    sid = f"s_{meta.get('character_id', 0)}_{meta['msg_id']}_{meta.get('seq', 0)}"
                    imp_info = importance_map.get(sid, {})
                    imp_raw = imp_info.get("importance", 5.0)
                    importance_score = max(0.0, min(1.0, (imp_raw - 1.0) / 9.0))

                # 实体匹配分数
                entity_score = 0.0
                if query_entities:
                    try:
                        doc_entities = set(e[0] for e in extract_entities_from_text(doc))
                        if doc_entities:
                            overlap = len(query_entities & doc_entities)
                            entity_score = min(1.0, overlap / len(query_entities))
                    except Exception:
                        pass

                # 访问频率分数（常被回忆的记忆更相关）
                access_score = 0.5
                if meta and meta.get("msg_id"):
                    sid = f"s_{meta.get('character_id', 0)}_{meta['msg_id']}_{meta.get('seq', 0)}"
                    imp_info = importance_map.get(sid, {})
                    access_count = imp_info.get("access_count", 0)
                    access_score = min(1.0, 0.5 + access_count * 0.1)

                # 情感上下文匹配（用户情绪化时优先回忆情感相关记忆）
                emotion_boost = 0.0
                from core.emotion_patterns import detect_emotion as _detect_emo
                query_emo = _detect_emo(query)
                if query_emo != "calm":
                    doc_emo = _detect_emo(doc)
                    if doc_emo == query_emo:
                        emotion_boost = 0.1  # 同类情感加成
                    elif doc_emo != "calm":
                        emotion_boost = 0.05  # 有情感但不同类型，小加成

                # 忽略惩罚：经常被检索到但不被选中的记忆降权
                ignored_penalty = 0.0
                if meta and meta.get("msg_id"):
                    sid = f"s_{meta.get('character_id', 0)}_{meta['msg_id']}_{meta.get('seq', 0)}"
                    imp_info = importance_map.get(sid, {})
                    ignored_cnt = imp_info.get("ignored_count", 0)
                    if ignored_cnt > 2:
                        ignored_penalty = min(0.3, ignored_cnt * 0.03)

                # 提及权重加成：doc 含用户反复提及的短语 → boost（上限 0.15）
                mention_boost = 0.0
                if mention_weights_map:
                    try:
                        import jieba
                        doc_phrases = {w for w in jieba.cut(doc) if len(w) >= 2 and len(w) <= 8}
                        max_w = 0.0
                        for p in doc_phrases:
                            w = mention_weights_map.get(p, 0.0)
                            if w > max_w:
                                max_w = w
                        mention_boost = min(0.15, max_w * 0.15)
                    except Exception:
                        pass

                # 最终分数：0.38×相似度 + 0.12×BM25 + 0.12×时效性 + 0.15×重要性 + 0.15×实体 + 0.06×访问频率 + 提及加成 + 情感加成 - 忽略惩罚
                hybrid = 0.38 * cos_score + 0.12 * bm25_norm + 0.12 * recency_score + 0.15 * importance_score + 0.15 * entity_score + 0.06 * access_score + mention_boost + emotion_boost - ignored_penalty
                scored.append((doc, dist, meta, hybrid, emb))

            scored.sort(key=lambda x: -x[3])
            # 实体重叠度过滤：降权与查询无关的候选
            if query_entities:
                for i, (doc, dist, meta, hybrid, emb) in enumerate(scored):
                    try:
                        doc_entities = set(e[0] for e in extract_entities_from_text(doc))
                        if doc_entities and len(query_entities & doc_entities) == 0:
                            scored[i] = (doc, dist + 0.3, meta, hybrid * 0.5, emb)
                    except Exception:
                        pass
                scored.sort(key=lambda x: -x[3])
            # MMR 多样性选择（Zep 方案）：避免返回重复话题的记忆
            mmr_result = _mmr_select(query_emb, scored, top_k, lambda_mult=0.7)
            # 语义去重：cos_sim>0.92 的只保留 hybrid 分高的（同一事件不同表述）
            mmr_result = _semantic_dedup(mmr_result)
            # 只更新 MMR 最终选中的结果的访问记录
            _update_access_batch(mmr_result)
            # 递增未被选中的候选的忽略计数（记忆退休机制）
            mmr_ids = {
                f"s_{m[2].get('character_id', 0)}_{m[2]['msg_id']}_{m[2].get('seq', 0)}"
                for m in mmr_result if m[2] and m[2].get("msg_id")
            }
            ignored_ids = []
            for s_doc, s_dist, s_meta, s_hybrid, s_emb in scored:
                if s_meta and s_meta.get("msg_id"):
                    sid = f"s_{s_meta.get('character_id', 0)}_{s_meta['msg_id']}_{s_meta.get('seq', 0)}"
                    if sid not in mmr_ids:
                        ignored_ids.append(sid)
            if ignored_ids:
                from core.db import increment_ignored_batch
                increment_ignored_batch(ignored_ids)
            if mmr_result:
                top_score = mmr_result[0][3] if len(mmr_result[0]) > 3 else 0.0
                logger.debug(f"[向量搜索] q={query[:30]!r} n_cand={len(scored)} ret={len(mmr_result)} top_hybrid={top_score:.3f}")
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
        logger.warning(f"[向量搜索] 查询失败: {e}")
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
        logger.warning(f"[知识库检索] 异常: {e}")
    return []


def search_memories(query: str, top_k: int = 5, character_id: int = 0) -> list[dict]:
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

        _where = {"character_id": character_id} if character_id else None
        results = collection.query(
            query_embeddings=[query_emb],
            n_results=top_k,
            where=_where,
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
        logger.warning(f"[记忆向量] 检索失败: {e}")
        return _keyword_search_memories(query, top_k)


def compress_results(results: list[dict], max_chars: int = 600, max_items: int = 4) -> list[dict]:
    """压缩记忆检索结果：保留最重要的内容，截断过长的条目

    用于 prompt 注入前压缩，节省 token 预算。

    Args:
        results: search_memories 返回的结果列表
        max_chars: 压缩后的总字符上限
        max_items: 最多保留的条目数

    Returns:
        压缩后的结果列表
    """
    if not results:
        return results

    # 1. 按分数排序
    sorted_items = sorted(results, key=lambda x: x.get("score", 0), reverse=True)

    # 2. 取前 max_items 条
    kept = sorted_items[:max_items]

    # 3. 截断每条内容
    max_per_item = max_chars // max(len(kept), 1)
    total = 0
    out = []
    for item in kept:
        value = item.get("value", "")
        if len(value) > max_per_item:
            # 保留开头和结尾的关键信息
            head = max_per_item // 2
            tail = max_per_item // 3
            item["value"] = value[:head] + "…" + value[-tail:] if len(value) > head + tail + 1 else value[:max_per_item]
        if total + len(item.get("value", "")) > max_chars:
            break
        total += len(item.get("value", ""))
        out.append(item)

    return out