# version: 5.0.0
"""夕语后端 —— 延迟加载版本，所有路由在 lifespan startup 中加载"""
import sys
import io
# Windows 控制台 UTF-8 输出，避免 GBK 编码错误
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from contextlib import asynccontextmanager
import importlib
import os
import logging
from core.retry import silent_exc
logger = logging.getLogger(__name__)

# ─── 启动阶段追踪 ───
_startup_stage = "importing"

# ─── 所有路由延迟加载列表 ───
_ALL_ROUTERS = [
    ("api.habits", "router"),
    ("api.settings", "router"),
    ("api.test", "router"),
    ("api.history", "router"),
    ("api.memory", "router"),
    ("api.summary", "router"),
    ("api.search", "router"),
    ("api.chat_manage", "router"),
    ("api.chat_sessions", "router"),
    ("api.rag", "router"),
    ("api.export", "router"),
    ("api.user_persona", "router"),
    ("api.avatar", "router"),
    ("api.countdowns", "router"),
    ("api.lorebook", "router"),
    ("api.migrate", "router"),
    ("api.split_sentences", "router"),
    ("api.knowledge", "router"),
    ("api.mcp", "router"),
    ("api.profile", "router"),
    ("api.episodic_memory", "router"),
    ("api.shared_memory", "router"),
    ("api.vision", "router"),
    ("api.cloud", "router"),
    ("api.tts", "router"),
    ("api.stt", "router"),
    ("api.emotion", "router"),
    ("api.relationship", "router"),
    ("api.demand", "router"),
    ("api.goal", "router"),
    ("api.favorites", "router"),
    ("api.stats", "router"),
    ("api.report", "router"),
    ("api.characters", "router"),
    ("api.debug", "router"),
    ("api.push", "router"),
    ("api.diagnose", "router"),
]

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
HAS_FRONTEND = os.path.exists(FRONTEND_DIR)

API_PREFIXES = ("settings", "chat", "countdowns",
                "memory", "summary", "search", "rag", "export", "avatar",
                "migrate", "test", "tts", "stt", "ws", "avatars", "api",
                "knowledge", "mcp", "profile", "vision", "cloud", "text",
                "emotion", "relationship", "demand", "goal", "favorites",
                "history", "split_sentences", "report", "stats")


@asynccontextmanager
async def lifespan(app):
    # 清理崩溃残留的备份键（A5-7）：仅当无活跃角色时清理
    try:
        from core.db import set_config, get_config
        from core.character_card import CharacterCard
        if not CharacterCard.get_active():
            for key in ("_previous_ai_name", "_previous_custom_system_prompt", "_previous_voice_config"):
                set_config(key, "")
    except Exception:
        pass

    # 启动 APScheduler 调度器
    from core.scheduler import start_scheduler, setup_default_jobs, shutdown_scheduler
    start_scheduler()
    setup_default_jobs()
    logger.info("[启动] APScheduler 调度器已启动")

    yield

    shutdown_scheduler()
    logger.info("[启动] APScheduler 调度器已关闭")


app = FastAPI(title="夕语后端 API", version="1.0.0", lifespan=lifespan)

# ─── 信任代理头（Nginx 反向代理）───
try:
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
    _trusted = os.environ.get("VESPER_TRUSTED_HOSTS", "127.0.0.1,localhost")
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=_trusted)
except ImportError:
    pass

# ─── CORS（云端模式限制 origins）───
_cors_origins = os.environ.get("VESPER_CORS_ORIGINS", "").split(",")
if _cors_origins == [""]:
    _cors_origins = ["http://127.0.0.1:8060", "http://127.0.0.1:8061", "http://127.0.0.1:8062",
                     "http://127.0.0.1:8063", "http://127.0.0.1:8064", "http://localhost:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Accept"],
)

# ─── 认证中间件 ───
from core.auth import AuthMiddleware, router as auth_router
if os.environ.get("VESPER_API_TOKEN"):
    app.add_middleware(AuthMiddleware)
    logger.info("[启动] 云端模式：已启用 Token 认证")
else:
    logger.info("[启动] 本地模式：Token 认证未启用")
app.include_router(auth_router)  # /auth/verify 始终可用

os.makedirs("data/avatars", exist_ok=True)
app.mount("/avatars", StaticFiles(directory="data/avatars"), name="avatars")

# 路由在模块级加载
_startup_stage = "loading_routes"
for mod_name, attr in _ALL_ROUTERS:
    try:
        mod = importlib.import_module(mod_name)
        app.include_router(getattr(mod, attr))
    except Exception as e:
        logger.warning(f"[启动] 加载路由 {mod_name} 失败: {e}")

_startup_stage = "ready"


@app.get("/health")
def health_check():
    """健康检查端点，返回服务状态和启动阶段"""
    return {"status": "ok", "ready": _startup_stage == "ready", "stage": _startup_stage}


@app.get("/")
def root():
    """根路径，返回前端页面或服务运行信息"""
    if HAS_FRONTEND:
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
    return {"message": "夕语后端服务运行中"}


@app.post("/api/window-theme")
def set_window_theme(data: dict):
    """设置窗口深色/浅色标题栏主题（仅 Windows）"""
    dark = bool(data.get("dark", True))
    if not isinstance(data.get("dark", None), (bool, type(None))):
        return {"status": "error", "message": "dark 参数必须是布尔值"}
    try:
        import ctypes
        from ctypes import wintypes
        hwnd_file = os.path.join("data", "hwnd.txt")
        hwnd = None
        if os.path.exists(hwnd_file):
            try:
                with open(hwnd_file) as f:
                    hwnd = int(f.read().strip())
            except Exception as e:
                silent_exc("set_window_theme", e)
        if not hwnd:
            hwnd = ctypes.windll.user32.FindWindowW(None, "夕语")
        if hwnd:
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            val = ctypes.c_int(1 if dark else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(hwnd), DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(val), ctypes.sizeof(val))
            return {"status": "ok"}
    except Exception as e:
        silent_exc("set_window_theme", e)
    return {"status": "ignored"}


# SPA fallback 必须注册在所有显式路由之后（包括 /health、/），否则 catch-all 会拦截它们
if HAS_FRONTEND:
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        """SPA 路由回退，非 API 路径返回前端静态文件或 index.html"""
        first = full_path.split("/")[0] if full_path else ""
        if first in API_PREFIXES:
            return JSONResponse({"detail": "Not Found"}, 404)
        raw = os.path.join(FRONTEND_DIR, full_path)
        real = os.path.realpath(raw)
        if not real.startswith(os.path.realpath(FRONTEND_DIR) + os.sep):
            return JSONResponse({"detail": "Not Found"}, 404)
        if os.path.isfile(real):
            return FileResponse(real)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    assets_dir = os.path.join(FRONTEND_DIR, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    else:
        logger.warning(f"[启动] 警告: assets 目录不存在 ({assets_dir})，前端静态资源将不可用")


@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 聊天端点，需 Token 认证"""
    from core.auth import verify_ws_token
    if not await verify_ws_token(websocket):
        await websocket.close(code=4001, reason="Unauthorized")
        return
    from api.chat import chat_websocket
    await chat_websocket(websocket)


# 生产环境由 launcher.py 启动，以下仅用于开发时直接运行 main.py
if __name__ == "__main__":
    import uvicorn, socket
    host = os.environ.get("VESPER_HOST", "127.0.0.1")
    port = int(os.environ.get("VESPER_PORT", "0"))

    if not port:
        def _dev_find_free_port(start=8001, end=8010):
            for p in range(start, end + 1):
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    if s.connect_ex(("127.0.0.1", p)) != 0:
                        return p
            return start
        port = _dev_find_free_port()

    os.makedirs("data", exist_ok=True)
    with open("data/port.txt", "w") as f:
        f.write(str(port))
    logger.info(f"[启动] 后端地址: {host}:{port}")
    uvicorn.run(app, host=host, port=port)
