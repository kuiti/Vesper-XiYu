# core/vector_store.py (延迟加载版本 — 重依赖在首次使用时才导入)
import os
import time
import threading
import warnings

CHROMA_PATH = "data/chroma_db"
os.makedirs(CHROMA_PATH, exist_ok=True)

_embedding_model = None
_model_loading = False
_model_loaded = False
_model_lock = threading.Lock()
_rebuild_lock = threading.Lock()

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        import os
        os.environ['HF_HUB_OFFLINE'] = '1'
        try:
            _embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2', local_files_only=True)
        except Exception:
            os.environ['HF_HUB_OFFLINE'] = '0'
            _embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
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

def get_collection(collection_name="chat_memory"):
    global _client_cache
    if _client_cache is None:
        import chromadb
        _client_cache = chromadb.PersistentClient(path=CHROMA_PATH)
    return _client_cache.get_or_create_collection(
        name=collection_name,
        # 余弦距离用于语义搜索：文本嵌入方向比欧氏距离更准确反映语义相似度
        metadata={"hnsw:space": "cosine"}
    )

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

def search_similar(query: str, top_k: int = 3):
    if not is_model_ready():
        return []
    try:
        model = get_embedding_model()
        query_emb = model.encode(query).tolist()
        collection = get_collection()
        results = collection.query(
            query_embeddings=[query_emb],
            n_results=top_k,
            include=["documents", "distances"]
        )
        if results and results['documents'] and results['documents'][0]:
            docs = results['documents'][0]
            distances = results['distances'][0] if results['distances'] else []
            return list(zip(docs, distances))
        return []
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
                    embeddings=all_data['embeddings'][i:end] if all_data['embeddings'] else None,
                    metadatas=all_data['metadatas'][i:end] if all_data['metadatas'] else None,
                    documents=all_data['documents'][i:end] if all_data['documents'] else None
                )
        try:
            client.delete_collection(temp_name)
        except Exception as e:
            print(f"[向量] 清理临时集合失败: {e}")
        print(f"[向量重建] 完成，共 {total} 条消息")
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