# core/vector_store/knowledge.py — 知识库向量操作：分块 + 文档/画像向量管理
import warnings
import logging
from .model import is_model_ready, get_embedding_model, get_collection

logger = logging.getLogger(__name__)


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