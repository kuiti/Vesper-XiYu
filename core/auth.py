# version: 1.0.0
"""夕语云端认证中间件 — Bearer Token 认证"""
import os
import time
import logging
from fastapi import Request, WebSocket, APIRouter
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

router = APIRouter(prefix="/auth", tags=["auth"])

# 登录失败日志（供 fail2ban 使用）
_auth_logger = logging.getLogger("sakura.auth")
_auth_logger.setLevel(logging.WARNING)
_LOG_PATH = "/var/log/vesper.log" if os.path.isdir("/var/log") else os.path.join("data", "vesper_auth.log")
os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
_handler = logging.FileHandler(_LOG_PATH)
_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
_auth_logger.addHandler(_handler)

# 登录失败限流：{ip: [timestamp, ...]}
_login_attempts: dict[str, list[float]] = {}
_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 300  # 5 分钟
_last_cleanup = 0.0  # 上次全局清理时间

# 白名单路径（不需要认证）
_WHITELIST_EXACT = ("/", "/health", "/favicon.ico", "/config.js", "/docs", "/openapi.json", "/redoc", "/auth/verify")
_WHITELIST_PREFIXES = ("/assets/", "/avatars/", "/tts/audio/")


def _get_token() -> str:
    """从环境变量读取 API Token"""
    return os.environ.get("VESPER_API_TOKEN", "")


def _is_cloud_mode() -> bool:
    """是否为云端模式（设置了 VESPER_API_TOKEN）"""
    return bool(_get_token())


class AuthMiddleware(BaseHTTPMiddleware):
    """Bearer Token 认证中间件"""

    async def dispatch(self, request: Request, call_next):
        token = _get_token()
        if not token:
            # 本地模式，不验证
            return await call_next(request)

        path = request.url.path

        # 白名单放行
        if path in _WHITELIST_EXACT:
            return await call_next(request)
        for prefix in _WHITELIST_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # 验证 Bearer Token
        auth_header = request.headers.get("Authorization", "")
        if auth_header == f"Bearer {token}":
            return await call_next(request)

        return JSONResponse({"detail": "Unauthorized"}, status_code=401)


async def verify_ws_token(websocket: WebSocket) -> bool:
    """验证 WebSocket 连接的 Token（从 query param 读取）"""
    token = _get_token()
    if not token:
        return True  # 本地模式，不验证

    ws_token = websocket.query_params.get("token", "")
    return ws_token == token


@router.post("/verify")
async def verify_token(request: Request):
    """验证 Token 是否正确（登录接口）"""
    client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if not client_ip:
        client_ip = request.headers.get("X-Real-IP", "")
    if not client_ip:
        client_ip = request.client.host if request.client else "unknown"

    # 检查限流
    now = time.time()
    # 定期清理所有过期 IP（每 10 分钟一次，防内存泄漏）
    global _last_cleanup
    if now - _last_cleanup > 600:
        _last_cleanup = now
        expired_ips = [ip for ip, ts in _login_attempts.items() if not ts or now - ts[-1] > _WINDOW_SECONDS]
        for ip in expired_ips:
            del _login_attempts[ip]
    attempts = _login_attempts.setdefault(client_ip, [])
    # 清理过期记录
    attempts[:] = [t for t in attempts if now - t < _WINDOW_SECONDS]
    if len(attempts) >= _MAX_ATTEMPTS:
        return JSONResponse({"ok": False, "error": "尝试次数过多，请5分钟后再试"}, status_code=429)

    # 解析请求体
    try:
        body = await request.json()
        token = body.get("token", "")
    except Exception:
        return JSONResponse({"ok": False, "error": "请求格式错误"}, status_code=400)

    # 验证 Token
    correct_token = _get_token()
    if not correct_token:
        return JSONResponse({"ok": True, "message": "本地模式，无需验证"})
    if token == correct_token:
        return JSONResponse({"ok": True, "message": "验证成功"})
    else:
        attempts.append(now)
        _auth_logger.warning(f"Token incorrect from {client_ip}")
        return JSONResponse({"ok": False, "error": "Token 不正确"}, status_code=401)
