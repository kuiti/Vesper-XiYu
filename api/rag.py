from fastapi import APIRouter, BackgroundTasks
from core.vector_store import rebuild_all_vectors, is_model_ready, get_collection

router = APIRouter(prefix="/rag", tags=["rag"])

def _check_installed():
    try:
        import sentence_transformers, chromadb
        return True
    except ImportError:
        return False

def rebuild_task():
    rebuild_all_vectors()

@router.post("/rebuild")
async def rebuild_index(background_tasks: BackgroundTasks):
    background_tasks.add_task(rebuild_task)
    return {"status": "started", "message": "索引重建已开始，请稍后查看"}

@router.get("/status")
async def rag_status():
    installed = _check_installed()
    model_ok = is_model_ready()
    count = 0
    if model_ok:
        try:
            col = get_collection()
            count = col.count()
        except Exception:
            pass
    return {"model_loaded": model_ok, "vector_count": count, "installed": installed}

@router.post("/install")
async def rag_install():
    if _check_installed():
        return {"ok": True, "msg": "向量引擎已安装，重启佐仓后自动加载模型"}
    try:
        import subprocess, sys
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", "sentence-transformers", "chromadb"],
            capture_output=True, text=True, timeout=300
        )
        if r.returncode == 0:
            return {"ok": True, "msg": "安装成功！模型约420MB，首次启动时自动下载。重启佐仓生效。"}
        return {"ok": False, "error": f"安装失败: {r.stderr[-200:]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}