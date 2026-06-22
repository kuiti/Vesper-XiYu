# launcher/process.py — 进程管理：僵尸清理、实例检测、端口管理、后端启动
import os
import sys
import threading
import socket
import time as _time
import logging
from . import _shared as _s

logger = logging.getLogger(__name__)


def _kill_zombie_processes():
    """启动前检查固定端口，清理僵尸进程（端口被占用但无 HTTP 响应）"""
    import urllib.request
    import subprocess
    killed = []
    for port in _s.FIXED_PORTS:
        # 先检查端口是否被监听
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        in_use = sock.connect_ex(("127.0.0.1", port)) == 0
        sock.close()
        if not in_use:
            continue
        # 端口被占用，发 HTTP 健康检查
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/health",
                headers={"User-Agent": "SakuraLauncher/1.0"}
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    continue  # 活的实例，跳过
        except Exception as e:
            logger.warning(f"[launcher] 僵尸检测 HTTP 检查失败 端口{port}: {e}")
        # 查找占用端口的 PID 并杀掉
        try:
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.split("\n"):
                if f"127.0.0.1:{port}" in line and "LISTENING" in line:
                    parts = line.strip().split()
                    pid = parts[-1]
                    subprocess.run(
                        ["taskkill", "/F", "/PID", pid],
                        capture_output=True, timeout=5
                    )
                    killed.append(f"端口{port}(PID:{pid})")
                    break
        except Exception as e:
            logger.warning(f"[启动] 清理端口{port}失败: {e}")
    if killed:
        logger.info(f"[启动] 已清理僵尸进程: {', '.join(killed)}")


def _find_existing_instance():
    """遍历5个固定端口，发HTTP健康检查，找到已运行的实例。
    返回 (port, response_text)，无实例返回 (None, None)。
    """
    import urllib.request
    for port in _s.FIXED_PORTS:
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/health",
                headers={"User-Agent": "SakuraLauncher/1.0"}
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                text = resp.read().decode('utf-8', errors='ignore')
                if resp.status == 200:
                    return port, text
        except Exception:
            continue
    return None, None


def _activate_existing_window(port):
    """尝试激活已有实例的窗口。先试命名管道，失败则用浏览器打开。"""
    import win32file
    pipe_name = f'\\\\.\\pipe\\sakura_ai_{port}'
    try:
        handle = win32file.CreateFile(
            pipe_name,
            win32file.GENERIC_READ | win32file.GENERIC_WRITE,
            0, None,
            win32file.OPEN_EXISTING,
            0, None)
        win32file.WriteFile(handle, b'show')
        _, resp = win32file.ReadFile(handle, 4096)
        win32file.CloseHandle(handle)
        if resp.decode('utf-8', errors='ignore').strip() == 'ok':
            logger.info(f"[启动] 已通过管道激活端口 {port} 的窗口")
            return
    except Exception as e:
        logger.warning(f"[launcher] 命名管道激活失败: {e}")
    # 管道失败，回退浏览器
    import webbrowser
    webbrowser.open(f"http://127.0.0.1:{port}/")
    logger.info(f"[启动] 浏览器打开 http://127.0.0.1:{port}/")


def _start_pipe_server(port):
    """在后台线程启动命名管道服务器（管道名包含端口号）"""
    import win32pipe, win32file
    pipe_name = f'\\\\.\\pipe\\sakura_ai_{port}'

    def _serve():
        while True:
            pipe = None
            try:
                pipe = win32pipe.CreateNamedPipe(
                    pipe_name,
                    win32pipe.PIPE_ACCESS_DUPLEX,
                    win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
                    1, 4096, 4096, 0, None)
                win32pipe.ConnectNamedPipe(pipe, None)
                _, data = win32file.ReadFile(pipe, 4096)
                cmd = data.decode('utf-8', errors='ignore').strip()
                resp = b'ok'
                if cmd == 'show':
                    from .tray import _on_tray_show
                    _on_tray_show(None, None)
                elif cmd == 'quit':
                    win32file.WriteFile(pipe, b'ok')
                    from .tray import _on_tray_quit
                    _on_tray_quit(None, None)
                    return
                elif cmd == 'ping':
                    resp = b'pong'
                win32file.WriteFile(pipe, resp)
            except Exception as e:
                logger.warning(f"[管道] 异常: {e}")
                _time.sleep(1)
            finally:
                if pipe:
                    try:
                        win32file.CloseHandle(pipe)
                    except Exception as e:
                        logger.warning(f"[launcher] 关闭管道句柄失败: {e}")

    t = threading.Thread(target=_serve, daemon=True)
    t.start()
    return t


def _find_free_port():
    """在5个固定端口中找第一个空闲端口"""
    for port in _s.FIXED_PORTS:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("所有端口(8060-8064)均被占用")


def start_backend(port):
    import uvicorn
    logger.info(f"[后端] 开始在端口 {port} 启动...")
    try:
        from main import app  # 延迟导入，不阻塞主线程
        logger.info(f"[后端] main 导入成功")
        os.makedirs("data", exist_ok=True)
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        server = uvicorn.Server(config)
        with open(os.path.join("data", "port.txt"), "w") as f:
            f.write(str(port))
        server.run()
    except Exception as e:
        try:
            with open(os.path.join("data", "startup_error.txt"), "w", encoding="utf-8") as f:
                f.write(f"{type(e).__name__}: {e}")
        except Exception as e:
            logger.warning(f"[launcher] 写入启动错误日志失败: {e}")
        raise