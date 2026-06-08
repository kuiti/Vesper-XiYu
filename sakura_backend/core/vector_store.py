# core/vector_store.py (延迟加载版本 — 重依赖在首次使用时才导入)
import os
import re
import time
import math
import threading
import warnings
from datetime import datetime

CHROMA_PATH = "data/chroma_db"
os.makedirs(CHROMA_PATH, exist_ok=True)

_embedding_model = None
_model_loading = False
_model_loaded = False
_model_lock = threading.Lock()
_rebuild_lock = threading.Lock()

def get_embedding_model():
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model
    with _model_lock:
        if _embedding_model is not None:
            return _embedding_model
        import os
        # 强制离线——国内服务器连不上 HuggingFace
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        from sentence_transformers import SentenceTransformer
        try:
            _embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        except Exception as e:
            print(f'[RAG] 本地模型加载失败: {e}')
            _embedding_model = None
    return _embedding_model

def ensure_model_loaded_async():
    """后台线程加载模型，不阻塞主线程"""
    global _model_loaded, _model_loading
    with _model_lock:
        if _model_loaded or _model_loading:
            return
        _model_loading = True
    def load():
        global _model_loaded
        try:
            get_embedding_model()  # 触发加载
            _model_loaded = True
            print("RAG 模型加载完成")
        except Exception as e:
            print(f"RAG 模型加载失败: {e}")
        finally:
            _model_loading = False
    threading.Thread(target=load, daemon=True).start()

def is_model_ready():
    return _model_loaded

_client_cache = None
_client_lock = threading.Lock()

def get_collection(collection_name="chat_memory"):
    global _client_cache
    with _client_lock:
        if _client_cache is None:
            import chromadb
            _client_cache = chromadb.PersistentClient(path=CHROMA_PATH)
    try:
        return _client_cache.get_collection(collection_name)
    except Exception:
        return _client_cache.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

def split_sentences(text: str) -> list:
    """按句号/感叹号/问号/换行分句，过滤空句和短句"""
    parts = re.split(r'(?<=[。！？!?\n])', text)
    return [s.strip() for s in parts if s.strip() and len(s.strip()) >= 2]


# ─── 重要性打分 ───
_DATE_PATTERN = re.compile(r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?|\d{1,2}月\d{1,2}[日号]?|明天|后天|下周|下个月')
_EMOTION_WORDS = re.compile(r'开心|难过|生气|伤心|高兴|兴奋|紧张|焦虑|害怕|担心|感动|失望|孤独|无聊|累|烦')
_IMPORTANT_WORDS = re.compile(r'考试|面试|生日|结婚|毕业|手术|住院|搬家|入职|离职|升职|分手|表白|求婚|怀孕|生孩子')
_PERSON_PLACE = re.compile(r'爸爸|妈妈|爷爷|奶奶|哥哥|姐姐|弟弟|妹妹|老师|老板|同事|朋友|同学|男朋友|女朋友|老公|老婆')


def calculate_importance(text: str, role: str = "user") -> float:
    """计算句子重要性分数（1-10），纯规则不调用LLM"""
    score = 5.0
    # 包含日期/时间 → +2
    if _DATE_PATTERN.search(text):
        score += 2.0
    # 包含人名/地名 → +1
    if _PERSON_PLACE.search(text):
        score += 1.0
    # 包含情感词 → +1
    if _EMOTION_WORDS.search(text):
        score += 1.0
    # 包含重要事件词 → +3
    if _IMPORTANT_WORDS.search(text):
        score += 3.0
    # 句子长度 > 50 字 → +1
    if len(text) > 50:
        score += 1.0
    # 用户消息 → +1（比 AI 回复重要）
    if role == "user":
        score += 1.0
    return max(1.0, min(10.0, score))


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
    except Exception:
        pass
    return False, None, None


def add_sentence_vectors(msg_id: int, text: str, role: str = "user"):
    """将消息按句拆分，批量嵌入存入 sentence_index 向量库，计算重要性，去重"""
    if not is_model_ready():
        return
    sentences = split_sentences(text)
    if not sentences:
        return
    model = get_embedding_model()
    collection = get_collection("sentence_index")
    # 批量编码所有句子（比逐句 encode 快 5-10 倍）
    embeddings = model.encode(sentences).tolist()
    try:
        from core.db import get_conn, set_memory_importance
        now = datetime.now().isoformat()
        with get_conn() as conn:
            cursor = conn.cursor()
            for seq, (sentence, embedding) in enumerate(zip(sentences, embeddings)):
                sid = f"s_{msg_id}_{seq}"

                # 去重检查
                is_dup, existing_id, existing_doc = _check_duplicate(collection, embedding, sentence)
                if is_dup and existing_id:
                    if len(sentence) > len(existing_doc):
                        cursor.execute("UPDATE sentence_index SET content = ?, msg_id = ?, seq = ?, created_at = ? WHERE content = ?",
                                      (sentence, msg_id, seq, now, existing_doc))
                        collection.upsert(
                            ids=[existing_id],
                            embeddings=[embedding],
                            metadatas=[{"msg_id": msg_id, "seq": seq, "role": role, "text": sentence[:200]}],
                            documents=[sentence]
                        )
                        importance = calculate_importance(sentence, role)
                        set_memory_importance(existing_id, importance, now)
                        print(f"[去重] 更新: {existing_doc[:30]} → {sentence[:30]}")
                    else:
                        print(f"[去重] 跳过: {sentence[:30]} (已有更长版本)")
                    continue

                cursor.execute("INSERT INTO sentence_index (msg_id, seq, content, created_at) VALUES (?, ?, ?, ?)",
                              (msg_id, seq, sentence, now))
                importance = calculate_importance(sentence, role)
                set_memory_importance(sid, importance, now)
                collection.upsert(
                    ids=[sid],
                    embeddings=[embedding],
                    metadatas=[{"msg_id": msg_id, "seq": seq, "role": role, "text": sentence[:200]}],
                    documents=[sentence]
                )
    except Exception as e:
        print(f"[句子索引] 写入失败: {e}")
    # 新消息写入后刷新 BM25 缓存
    global _bm25, _bm25_docs
    _bm25 = None
    _bm25_docs = None


def add_message_vector(msg_id: str, text: str, metadata: dict = None):
    if not is_model_ready():
        return
    # 过滤短消息噪声：少于5个字符的消息不建立向量索引
    if not text or len(text.strip()) < 5:
        return
    model = get_embedding_model()
    try:
        embedding = model.encode(text).tolist()
        collection = get_collection()
        collection.upsert(
            ids=[msg_id],
            embeddings=[embedding],
            metadatas=[metadata or {"text": text[:200]}],
            documents=[text]
        )
    except Exception as e:
        warnings.warn(f"向量索引失败（{msg_id}）：{str(e)}")
    # 新消息写入后刷新 BM25 缓存
    global _bm25, _bm25_docs
    _bm25 = None
    _bm25_docs = None

_bm25 = None
_bm25_docs = None

def _tokenize(text):
    """中文分词：优先用 jieba，回退空格分词"""
    try:
        import jieba
        return list(jieba.cut(text))
    except ImportError:
        return text.split()


def _get_bm25(collection_name: str = None):
    global _bm25, _bm25_docs
    try:
        col = get_collection(collection_name)
        data = col.get(include=["documents"])
        docs = data.get("documents", [])
        if not docs:
            return None
        if _bm25_docs != docs:
            from rank_bm25 import BM25Okapi
            tokenized = [_tokenize(d) for d in docs]
            _bm25 = BM25Okapi(tokenized)
            _bm25_docs = docs
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
    except Exception:
        pass


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
    global _bm25, _bm25_docs  # 切换 collection 时需重置 BM25 缓存
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
            _bm25 = None  # 切换 collection，重置 BM25 缓存
            _bm25_docs = None
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
        from datetime import datetime
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
                    idx = _bm25_docs.index(doc) if _bm25_docs else -1
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

def rebuild_all_vectors(progress_callback=None):
    if not _rebuild_lock.acquire(blocking=False):
        print("[向量重建] 已有重建任务在进行中，跳过")
        return
    try:
        from core.db import get_all_chat_messages
        messages = get_all_chat_messages()
        if not messages:
            return
        import chromadb
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        model = get_embedding_model()

        # 安全重建：先写临时集合，成功后再替换旧集合
        temp_name = "chat_memory_rebuild"
        try:
            client.delete_collection(temp_name)
        except Exception as e:
            print(f"[向量] 清理临时集合失败: {e}")
        temp_collection = client.get_or_create_collection(
            name=temp_name, metadata={"hnsw:space": "cosine"}
        )

        total = len(messages)
        for idx, msg in enumerate(messages):
            msg_id = f"{msg['role']}_{msg.get('timestamp', 'unknown')}_{idx}"
            text = msg['content']
            if text and len(text.strip()) >= 5:
                embedding = model.encode(text).tolist()
                temp_collection.upsert(
                    ids=[msg_id],
                    embeddings=[embedding],
                    metadatas=[{"role": msg['role'], "timestamp": msg.get('timestamp', '')}],
                    documents=[text]
                )
            if progress_callback and (idx + 1) % 50 == 0:
                progress_callback(idx + 1, total)

        # 重建成功，替换旧集合
        try:
            client.delete_collection("chat_memory")
        except Exception as e:
            print(f"[向量] 清理旧集合失败: {e}")
        new_collection = client.get_or_create_collection(
            name="chat_memory", metadata={"hnsw:space": "cosine"}
        )
        all_data = temp_collection.get(include=["embeddings", "metadatas", "documents"])
        if all_data and all_data['ids']:
            batch_size = 500
            for i in range(0, len(all_data['ids']), batch_size):
                end = min(i + batch_size, len(all_data['ids']))
                new_collection.upsert(
                    ids=all_data['ids'][i:end],
                    embeddings=all_data['embeddings'][i:end] if len(all_data['embeddings']) > 0 else None,
                    metadatas=all_data['metadatas'][i:end] if all_data['metadatas'] else None,
                    documents=all_data['documents'][i:end] if all_data['documents'] else None
                )
        try:
            client.delete_collection(temp_name)
        except Exception as e:
            print(f"[向量] 清理临时集合失败: {e}")

        # 重建 sentence_index 集合
        try:
            from core.db import get_conn
            with get_conn() as conn:
                rows = conn.execute("SELECT sid, content FROM sentence_index WHERE content IS NOT NULL AND length(content) >= 5").fetchall()
            if rows:
                try:
                    client.delete_collection("sentence_index")
                except Exception:
                    pass
                sent_collection = client.get_or_create_collection(
                    name="sentence_index", metadata={"hnsw:space": "cosine"}
                )
                for r in rows:
                    embedding = model.encode(r["content"]).tolist()
                    sid = str(r['sid'])  # sid 格式已是 "s_{msg_id}_{seq}"
                    sent_collection.upsert(
                        ids=[sid],
                        embeddings=[embedding],
                        metadatas=[{"msg_id": int(sid.split('_')[1]) if '_' in sid else 0, "seq": int(sid.split('_')[2]) if sid.count('_') >= 2 else 0, "role": "assistant"}],
                        documents=[r["content"]]
                    )
                print(f"[向量重建] sentence_index: {len(rows)} 条")
        except Exception as e:
            print(f"[向量重建] sentence_index 失败: {e}")

        print(f"[向量重建] 完成，共 {total} 条消息")
        global _client_cache, _bm25, _bm25_docs
        _client_cache = None
        _bm25 = None
        _bm25_docs = None
    finally:
        _rebuild_lock.release()

# ===== 知识库扩展 =====

def chunk_text(text, max_chars=500, overlap=50):
    """按段落+字符边界分块，段落以空行为界"""
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    chunks = []
    for para in paragraphs:
        if len(para) <= max_chars:
            chunks.append(para)
        else:
            start = 0
            while start < len(para):
                end = min(start + max_chars, len(para))
                if end < len(para):
                    for sep in ['。', '！', '？', '.', '!', '?', '\n']:
                        pos = para.rfind(sep, start + max_chars // 2, end)
                        if pos > 0:
                            end = pos + 1
                            break
                chunks.append(para[start:end].strip())
                start = end - overlap if end - overlap > start else end
    return [c for c in chunks if len(c) >= 10]

def add_document_vectors(doc_id, chunks, filename=""):
    """将文档分块嵌入并存入 knowledge_base 集合"""
    if not is_model_ready():
        return 0
    model = get_embedding_model()
    collection = get_collection("knowledge_base")
    count = 0
    for i, chunk in enumerate(chunks):
        if len(chunk.strip()) < 10:
            continue
        try:
            embedding = model.encode(chunk).tolist()
            collection.upsert(
                ids=[f"doc_{doc_id}_chunk_{i}"],
                embeddings=[embedding],
                metadatas=[{"doc_id": str(doc_id), "chunk_index": i, "filename": filename}],
                documents=[chunk]
            )
            count += 1
        except Exception as e:
            warnings.warn(f"知识库向量索引失败（doc_{doc_id}_chunk_{i}）：{str(e)}")
    return count

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

def delete_document_vectors(doc_id):
    """删除指定文档的所有向量"""
    if not is_model_ready():
        return
    collection = get_collection("knowledge_base")
    try:
        results = collection.get(where={"doc_id": str(doc_id)})
        if results and results['ids']:
            collection.delete(ids=results['ids'])
    except Exception as e:
        print(f"[知识库删除] 异常: {e}")

# 启动异步加载模型
ensure_model_loaded_async()


# ─── 记忆向量存储（memory + user_profile 向量化）───

def add_memory_vector(key: str, value: str, meta: dict = None) -> bool:
    """将 memory 表的一条记录写入向量库"""
    if not is_model_ready() or not value or len(value.strip()) < 5:
        return False
    try:
        model = get_embedding_model()
        embedding = model.encode(value).tolist()
        collection = get_collection("memory_store")
        collection.upsert(
            ids=[f"mem_{key}"],
            embeddings=[embedding],
            metadatas=[{
                "key": key,
                "type": meta.get("type", "memory") if meta else "memory",
                "text": value[:200],
            }],
            documents=[value]
        )
        return True
    except Exception as e:
        print(f"[记忆向量] 写入失败: key={key} {e}")
        return False


def add_profile_vectors():
    """将 user_profile 中有意义的画像写入向量库"""
    if not is_model_ready():
        return
    try:
        from core.db import get_conn
        model = get_embedding_model()
        collection = get_collection("memory_store")
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value, confidence FROM user_profile WHERE confidence >= 0.6")
            rows = cursor.fetchall()
        count = 0
        for r in rows:
            key = r["key"]
            value = r["value"]
            if not value or len(value) < 5:
                continue
            try:
                import json
                val = json.loads(value) if isinstance(value, str) and (value.startswith("{") or value.startswith("[")) else value
                text = val.get("text", value) if isinstance(val, dict) else str(value)
            except (json.JSONDecodeError, AttributeError):
                text = str(value)
            if len(text) < 5:
                continue
            embedding = model.encode(text).tolist()
            collection.upsert(
                ids=[f"profile_{key}"],
                embeddings=[embedding],
                metadatas=[{"key": key, "type": "profile", "text": text[:200]}],
                documents=[text]
            )
            count += 1
        if count:
            print(f"[记忆向量] 同步了 {count} 条 user_profile")
    except Exception as e:
        print(f"[记忆向量] user_profile 同步失败: {e}")


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
    except Exception:
        pass

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
    except Exception:
        pass

    return results[:top_k]


def sync_memories_to_vector():
    """后台同步：将 memory 表和 user_profile 写入向量库（去重）"""
    if not is_model_ready():
        return
    try:
        # memory 表
        from core.db import get_conn
        model = get_embedding_model()
        collection = get_collection("memory_store")
        count = 0
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM memory")
            rows = cursor.fetchall()
        for r in rows:
            key = r["key"]
            value = r["value"]
            if not value or len(value) < 5:
                continue
            # 检查是否已存在
            existing = collection.get(ids=[f"mem_{key}"])
            if existing and existing.get("ids"):
                continue
            embedding = model.encode(value).tolist()
            collection.upsert(
                ids=[f"mem_{key}"],
                embeddings=[embedding],
                metadatas=[{"key": key, "type": "memory", "text": value[:200]}],
                documents=[value]
            )
            count += 1
        if count:
            print(f"[记忆向量] 同步了 {count} 条 memory")
        # user_profile
        add_profile_vectors()
    except Exception as e:
        print(f"[记忆向量] 同步失败: {e}")