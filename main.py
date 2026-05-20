# version: 3.8.1
from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api.chat import chat_websocket
from api.history import router as history_router
from api.todos import router as todos_router
from api.notes import router as notes_router
from api.settings import router as settings_router
from api.memory import router as memory_router
from api.summary import router as summary_router
from api.search import router as search_router
from api.chat_manage import router as chat_manage_router
from api.rag import router as rag_router
from api.export import router as export_router
from api.avatar import router as avatar_router
from api.location import router as location_router
from api.countdowns import router as countdowns_router
from api.reminders import router as reminders_router
from api.test import router as test_router
from api.migrate import router as migrate_router
from api.split_sentences import router as split_router
import os

app = FastAPI(title="Vesper后端 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录（头像）
os.makedirs("data/avatars", exist_ok=True)
app.mount("/avatars", StaticFiles(directory="data/avatars"), name="avatars")

# 注册 API 路由
app.include_router(history_router)
app.include_router(todos_router)
app.include_router(notes_router)
app.include_router(settings_router)
app.include_router(memory_router)
app.include_router(summary_router)
app.include_router(search_router)
app.include_router(chat_manage_router)
app.include_router(rag_router)
app.include_router(export_router)
app.include_router(avatar_router)
app.include_router(location_router)
app.include_router(countdowns_router)
app.include_router(reminders_router)
app.include_router(test_router)
app.include_router(migrate_router)
app.include_router(split_router)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
HAS_FRONTEND = os.path.exists(FRONTEND_DIR)

if HAS_FRONTEND:
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="assets")

@app.get("/")
def root():
    if HAS_FRONTEND:
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
    return {"message": "Vesper后端服务运行中"}


@app.post("/api/window-theme")
def set_window_theme(data: dict):
    """Set Windows title bar dark/light mode."""
    dark = data.get("dark", True)
    try:
        import ctypes
        from ctypes import wintypes
        # Try stored HWND first
        hwnd_file = os.path.join("data", "hwnd.txt")
        hwnd = None
        if os.path.exists(hwnd_file):
            try:
                with open(hwnd_file) as f:
                    hwnd = int(f.read().strip())
            except Exception:
                pass
        # Fallback: find by title
        if not hwnd:
            hwnd = ctypes.windll.user32.FindWindowW(None, "Vesper")
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

API_PREFIXES = ("settings", "chat", "todos", "notes", "countdowns", "reminders",
                "memory", "summary", "search", "rag", "export", "avatar", "location",
                "migrate", "test", "tts", "stt", "ws", "avatars", "assets", "api")

if HAS_FRONTEND:
    from fastapi.responses import JSONResponse

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        first = full_path.split("/")[0] if full_path else ""
        if first in API_PREFIXES:
            return JSONResponse({"detail": "Not Found"}, 404)
        # Prevent path traversal: resolve and verify within FRONTEND_DIR
        raw = os.path.join(FRONTEND_DIR, full_path)
        real = os.path.realpath(raw)
        if not real.startswith(os.path.realpath(FRONTEND_DIR) + os.sep):
            return JSONResponse({"detail": "Not Found"}, 404)
        if os.path.isfile(real):
            return FileResponse(real)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await chat_websocket(websocket)

def find_free_port(start=8001, end=8010):
    import socket
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start

if __name__ == "__main__":
    import uvicorn
    port = find_free_port()
    os.makedirs("data", exist_ok=True)
    with open("data/port.txt", "w") as f:
        f.write(str(port))
    print(f"后端端口: {port}")
    uvicorn.run(app, host="127.0.0.1", port=port)