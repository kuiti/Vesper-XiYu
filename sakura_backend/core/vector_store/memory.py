# core/vector_store/memory.py — 记忆向量操作：句子/消息/记忆的向量写入与删除
import warnings
from datetime import datetime
import logging
from .model import is_model_ready, get_embedding_model, get_collection
from .utils import split_sentences, calculate_importance
from .search import _check_duplicate
from .bm25 import reset_bm25_cache

logger = logging.getLogger(__name__)


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
    reset_bm25_cache()


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
    reset_bm25_cache()


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


def delete_message_vectors(msg_id):
    """删除单条消息的向量（避免全量重建）"""
    if not is_model_ready():
        return
    try:
        # 主集合：chat_memory 以 msg_id 为 id
        main = get_collection()
        main.delete(ids=[str(msg_id)])
    except Exception as e:
        print(f"[向量删除] chat_memory: {e}")
    try:
        # 句子索引集合：按 msg_id 过滤删除
        sent = get_collection("sentence_index")
        results = sent.get(where={"msg_id": msg_id})
        if results and results['ids']:
            sent.delete(ids=results['ids'])
    except Exception as e:
        print(f"[向量删除] sentence_index: {e}")


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
        from .knowledge import add_profile_vectors
        add_profile_vectors()
    except Exception as e:
        print(f"[记忆向量] 同步失败: {e}")