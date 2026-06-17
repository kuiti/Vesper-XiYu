# core/vector_store/ — 向量存储包
# 从子模块导出所有公共函数，保持旧 import 兼容
# 例如: from core.vector_store import search_similar  仍然可用

from .model import (
    CHROMA_PATH,
    get_embedding_model,
    ensure_model_loaded_async,
    is_model_ready,
    get_collection,
    reset_client_cache,
    _rebuild_lock,
)

from .utils import (
    split_sentences,
    calculate_importance,
)

from .bm25 import (
    _tokenize,
    _get_bm25,
    _update_access_batch,
    _keyword_search_memories,
    reset_bm25_cache,
)

from .search import (
    _check_duplicate,
    _mmr_select,
    search_similar,
    search_knowledge_similar,
    search_memories,
)

from .memory import (
    add_sentence_vectors,
    add_message_vector,
    add_memory_vector,
    delete_message_vectors,
    sync_memories_to_vector,
)

from .knowledge import (
    chunk_text,
    add_document_vectors,
    delete_document_vectors,
    add_profile_vectors,
)

import logging
from core.retry import silent_exc

logger = logging.getLogger(__name__)


def rebuild_all_vectors(progress_callback=None):
    """重建所有向量索引（安全模式：先写临时集合，成功后替换旧集合）"""
    if not _rebuild_lock.acquire(blocking=False):
        logger.warning("[向量重建] 已有重建任务在进行中，跳过")
        return
    try:
        from core.db import get_all_chat_messages
        import chromadb

        messages = get_all_chat_messages()
        if not messages:
            return
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        model = get_embedding_model()

        # 安全重建：先写临时集合，成功后再替换旧集合
        temp_name = "chat_memory_rebuild"
        try:
            client.delete_collection(temp_name)
        except Exception as e:
            logger.warning(f"[向量] 清理临时集合失败: {e}")
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
            logger.warning(f"[向量] 清理旧集合失败: {e}")
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
            logger.warning(f"[向量] 清理临时集合失败: {e}")

        # 重建 sentence_index 集合
        try:
            from core.db import get_conn
            with get_conn() as conn:
                rows = conn.execute("SELECT sid, content FROM sentence_index WHERE content IS NOT NULL AND length(content) >= 5").fetchall()
            if rows:
                try:
                    client.delete_collection("sentence_index")
                except Exception as e:
                    silent_exc("rebuild_all_vectors.delete_sentence_index", e)
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
                logger.info(f"[向量重建] sentence_index: {len(rows)} 条")
        except Exception as e:
            logger.warning(f"[向量重建] sentence_index 失败: {e}")

        logger.info(f"[向量重建] 完成，共 {total} 条消息")
        reset_client_cache()
        reset_bm25_cache()
    finally:
        _rebuild_lock.release()


# 启动异步加载模型
ensure_model_loaded_async()