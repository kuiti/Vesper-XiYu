"""诊断 API — 系统健康自检"""
from fastapi import APIRouter
from core.health import run_diagnostics

router = APIRouter(prefix="/diagnose", tags=["diagnose"])


@router.get("/health")
async def health_check():
    """完整系统健康检查"""
    return run_diagnostics()


@router.get("/ping")
async def ping():
    """轻量存活检查"""
    return {"status": "ok", "message": "pong"}
