# core/vector_store.py (异步加载模型版本)
import os
import time
import threading
import warnings
from sentence_transformers import SentenceTransformer
import chromadb

CHROMA_PATH = "data/chroma_db"
os.makedirs(CHROMA_PATH, exist_ok=True)

_embedding_model = None
_model_loading = False
_model_loaded = False

def get_embedding_model():
    global _embedding_model
    # 懒加载：首次调用触发模型下载和加载（~500MB），后续调用复用缓存实例
    if _embedding_model is None:
        _embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    return _embedding_model

def ensure_model_loaded_async():
    """后台线程加载模型，不阻塞主线程"""
    global _model_loaded, _model_loading
    # 双重检查锁定：CPython GIL 使其在实践中线程安全，无竞态
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
        _client_cache = chromadb.PersistentClient(path=CHROMA_PATH)
    # 余弦距离用于语义搜索：文本嵌入在高维空间中的方向比欧氏距离更准确地反映语义相似度
    return _client_cache.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )

def add_message_vector(msg_id: str, text: str, metadata: dict = None):
    if not is_model_ready():
        return
    # 过滤短消息噪声：少于5个字符的消息（单字回复、"嗯"、"好的"等）不建立向量索引
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

def rebuild_all_vectors(progress_callback=None):
    from core.db import get_all_chat_messages
    messages = get_all_chat_messages()
    if not messages:
        return
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    # 破坏性操作：删除集合并重建。若中途失败（OOM/模型加载失败）将丢失全部向量索引
    try:
        client.delete_collection("chat_memory")
    except:
        pass
    collection = get_collection()
    model = get_embedding_model()
    total = len(messages)
    for idx, msg in enumerate(messages):
        msg_id = f"{msg['role']}_{msg.get('timestamp', 'unknown')}_{idx}"
        text = msg['content']
        if text and len(text.strip()) >= 5:
            embedding = model.encode(text).tolist()
            collection.upsert(
                ids=[msg_id],
                embeddings=[embedding],
                metadatas=[{"role": msg['role'], "timestamp": msg.get('timestamp', '')}],
                documents=[text]
            )
        if progress_callback and (idx + 1) % 50 == 0:
            progress_callback(idx + 1, total)
        time.sleep(0.01)

# 启动异步加载模型
ensure_model_loaded_async()