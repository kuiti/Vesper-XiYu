# version: 5.0.0
"""夕语后端 —— 延迟加载版本，所有路由在 lifespan startup 中加载"""
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from contextlib import asynccontextmanager
import importlib
import os
import asyncio

# ─── 启动阶段追踪 ───
_startup_stage = "importing"

# ─── 所有路由延迟加载列表 ───
_ALL_ROUTERS = [
    ("api.settings", "router"),
    ("api.test", "router"),
    ("api.location", "router"),
    ("api.history", "router"),
    ("api.todos", "router"),
    ("api.notes", "router"),
    ("api.memory", "router"),
    ("api.summary", "router"),
    ("api.search", "router"),
    ("api.chat_manage", "router"),
    ("api.rag", "router"),
    ("api.export", "router"),
    ("api.avatar", "router"),
    ("api.countdowns", "router"),
    ("api.reminders", "router"),
    ("api.migrate", "router"),
    ("api.split_sentences", "router"),
    ("api.knowledge", "router"),
    ("api.mcp", "router"),
    ("api.profile", "router"),
    ("api.schedule", "router"),
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
]

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
HAS_FRONTEND = os.path.exists(FRONTEND_DIR)

API_PREFIXES = ("settings", "chat", "todos", "notes", "countdowns", "reminders",
                "memory", "summary", "search", "rag", "export", "avatar", "location",
                "migrate", "test", "tts", "stt", "ws", "avatars", "api",
                "knowledge", "mcp", "profile", "schedule", "vision", "cloud", "text",
                "emotion", "relationship", "demand", "goal", "favorites",
                "history", "split_sentences", "report", "stats")


@asynccontextmanager
async def lifespan(app):
    # 启动天气定时推送调度器
    from api.chat import weather_scheduler
    weather_task = asyncio.create_task(weather_scheduler())
    print("[启动] 天气调度器已启动")

    yield

    weather_task.cancel()
    try:
        await weather_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="夕语后端 API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("data/avatars", exist_ok=True)
app.mount("/avatars", StaticFiles(directory="data/avatars"), name="avatars")

# 路由在模块级加载
_startup_stage = "loading_routes"
for mod_name, attr in _ALL_ROUTERS:
    try:
        mod = importlib.import_module(mod_name)
        app.include_router(getattr(mod, attr))
    except Exception as e:
        print(f"[启动] 加载路由 {mod_name} 失败: {e}")

_startup_stage = "ready"


@app.get("/health")
def health_check():
    return {"status": "ok", "ready": _startup_stage == "ready", "stage": _startup_stage}


@app.get("/")
def root():
    if HAS_FRONTEND:
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
    return {"message": "夕语后端服务运行中"}


@app.post("/api/window-theme")
def set_window_theme(data: dict):
    dark = data.get("dark", True)
    try:
        import ctypes
        from ctypes import wintypes
        hwnd_file = os.path.join("data", "hwnd.txt")
        hwnd = None
        if os.path.exists(hwnd_file):
            try:
                with open(hwnd_file) as f:
                    hwnd = int(f.read().strip())
            except Exception:
                pass
        if not hwnd:
            hwnd = ctypes.windll.user32.FindWindowW(None, "夕语")
        if hwnd:
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            val = ctypes.c_int(1 if dark else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(hwnd), DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(val), ctypes.sizeof(val))
            return {"status": "ok"}
    except Exception:
        pass
    return {"status": "ignored"}


# SPA fallback 必须注册在所有显式路由之后（包括 /health、/），否则 catch-all 会拦截它们
if HAS_FRONTEND:
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
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
        print(f"[启动] 警告: assets 目录不存在 ({assets_dir})，前端静态资源将不可用")


@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    from api.chat import chat_websocket
    await chat_websocket(websocket)


# 生产环境由 launcher.py 启动，以下仅用于开发时直接运行 main.py
if __name__ == "__main__":
    import uvicorn, socket
    def _dev_find_free_port(start=8001, end=8010):
        for port in range(start, end + 1):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", port)) != 0:
                    return port
        return start
    port = _dev_find_free_port()
    os.makedirs("data", exist_ok=True)
    with open("data/port.txt", "w") as f:
        f.write(str(port))
    print(f"[开发] 后端端口: {port}")
    uvicorn.run(app, host="127.0.0.1", port=port)
