# core/vector_store/model.py — 全局状态 + embedding 模型管理
import os
import threading
import logging

logger = logging.getLogger(__name__)

CHROMA_PATH = "data/chroma_db"
os.makedirs(CHROMA_PATH, exist_ok=True)

_embedding_model = None
_model_loading = False
_model_loaded = False
_model_lock = threading.Lock()
_rebuild_lock = threading.Lock()

_client_cache = None
_client_lock = threading.Lock()


def get_embedding_model():
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model
    with _model_lock:
        if _embedding_model is not None:
            return _embedding_model
        import os
        # 设置 HuggingFace 镜像（国内用户可加速下载）
        os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
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


def reset_client_cache():
    """重置 ChromaDB 客户端缓存（重建向量后调用）"""
    global _client_cache
    _client_cache = None