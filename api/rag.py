from fastapi import APIRouter, BackgroundTasks
from core.vector_store import rebuild_all_vectors, is_model_ready, get_collection

router = APIRouter(prefix="/rag", tags=["rag"])

def rebuild_task():
    rebuild_all_vectors()

@router.post("/rebuild")
async def rebuild_index(background_tasks: BackgroundTasks):
    background_tasks.add_task(rebuild_task)
    return {"status": "started", "message": "索引重建已开始，请稍后查看"}

@router.get("/status")
async def rag_status():
    model_ok = is_model_ready()
    try:
        col = get_collection()
        count = col.count()
    except:
        count = 0
    return {"model_loaded": model_ok, "vector_count": count}