"""RAG 向量检索 API —— 索引重建、状态查询和依赖安装。"""
from fastapi import APIRouter, BackgroundTasks
from core.vector_store import rebuild_all_vectors, is_model_ready, get_collection
import logging
from core.retry import silent_exc
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"])

def _check_installed():
    """检查 sentence_transformers 和 chromadb 是否已安装。"""
    try:
        import sentence_transformers, chromadb
        return True
    except ImportError:
        return False

def rebuild_task():
    """后台重建全部向量索引。"""
    rebuild_all_vectors()

@router.post("/rebuild")
async def rebuild_index(background_tasks: BackgroundTasks):
    """触发后台向量索引重建。"""
    background_tasks.add_task(rebuild_task)
    return {"status": "started", "message": "索引重建已开始，请稍后查看"}

@router.get("/status")
async def rag_status():
    """查询 RAG 引擎状态（模型加载、向量数量）。"""
    installed = _check_installed()
    model_ok = is_model_ready()
    count = 0
    sentence_count = 0
    if model_ok:
        try:
            col = get_collection()
            count = col.count()
        except Exception as e:
            silent_exc("rag_status", e)
        try:
            col2 = get_collection("sentence_index")
            sentence_count = col2.count()
        except Exception as e:
            silent_exc("rag_status", e)
    return {"model_loaded": model_ok, "vector_count": count, "sentence_count": sentence_count, "total_vectors": count + sentence_count, "installed": installed}

@router.post("/install")
async def rag_install():
    """安装 RAG 依赖（sentence-transformers + chromadb）。"""
    from core.auth import _get_token
    if _get_token():
        return {"ok": False, "error": "云端模式不允许远程安装依赖"}
    if _check_installed():
        return {"ok": True, "msg": "向量引擎已安装"}
    try:
        import subprocess, sys
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", "sentence-transformers", "chromadb"],
            capture_output=True, text=True, timeout=300
        )
        if r.returncode == 0:
            return {"ok": True, "msg": "安装成功！模型约420MB，首次启动时自动下载。重启夕语生效。"}
        return {"ok": False, "error": "安装失败，请查看终端日志"}
    except Exception as e:
        return {"ok": False, "error": str(e)}