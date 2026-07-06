# launcher/lock.py — 文件锁单实例检测
"""launcher 锁文件模块——基于文件的单实例检测"""
import os
import json as _json
import ctypes
import logging
from . import _shared as _s

logger = logging.getLogger(__name__)


def _check_instance_lock():
    """检查文件锁。返回 (port, pid) 如果已有活实例，否则 (None, None)"""
    if not os.path.exists(_s.LOCK_FILE):
        return None, None
    try:
        with open(_s.LOCK_FILE, "r", encoding="utf-8") as f:
            data = _json.load(f)
        pid = data.get("pid")
        port = data.get("port")
        if pid and _is_pid_alive(pid):
            return port, pid
        # 僵尸锁（进程已死），清理
        os.remove(_s.LOCK_FILE)
    except Exception as e:
        logger.warning(f"[launcher] 读取锁文件失败: {e}")
        try:
            os.remove(_s.LOCK_FILE)
        except OSError:
            pass
    return None, None


def _is_pid_alive(pid):
    """检查 PID 是否存活（Windows）"""
    import ctypes.wintypes as _w32
    PROCESS_QUERY_INFORMATION = 0x0400
    try:
        h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
        if not h:
            return False
        code = _w32.DWORD()
        ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return code.value == 259  # STILL_ACTIVE
    except Exception:
        return False  # 无法判断时假定已死，不阻止启动


def _write_instance_lock(port):
    """写入当前实例的锁文件"""
    try:
        with open(_s.LOCK_FILE, "w", encoding="utf-8") as f:
            _json.dump({"pid": os.getpid(), "port": port}, f)
    except Exception as e:
        logger.warning(f"[启动] 写入锁文件失败: {e}")