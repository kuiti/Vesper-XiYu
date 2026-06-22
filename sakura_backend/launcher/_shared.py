# launcher/_shared.py — 共享常量、全局状态、基础初始化
# 所有子模块从这里 import，避免循环依赖
import sys
import os
import threading
import ctypes
import json as _json
import time as _time
import socket
import logging

logger = logging.getLogger(__name__)

# ─── BASE_DIR 计算 ───
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    MEIPASS = getattr(sys, '_MEIPASS', None)
    if MEIPASS:
        import shutil as _shutil
        for _item in ['frontend', 'data', 'config.json']:
            _src = os.path.join(MEIPASS, _item)
            _dst = os.path.join(BASE_DIR, _item)
            if os.path.exists(_src) and not os.path.exists(_dst):
                try:
                    if os.path.isdir(_src):
                        _shutil.copytree(_src, _dst)
                    else:
                        _shutil.copy2(_src, _dst)
                except Exception as e:
                    logger.warning(f"[启动] 复制资源失败 {_item}: {e}")
    try:
        import certifi
        os.environ['SSL_CERT_FILE'] = certifi.where()
        os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
    except Exception as e:
        logger.warning(f"[启动] certifi SSL 设置失败: {e}")
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 开发模式下也需要 SSL 证书
try:
    import certifi
    _cacert = certifi.where()
    os.environ['SSL_CERT_FILE'] = _cacert
    os.environ['REQUESTS_CA_BUNDLE'] = _cacert
    os.environ['CURL_CA_BUNDLE'] = _cacert
    os.environ['PIP_CERT'] = _cacert
    os.environ['SSL_CERT_DIR'] = os.path.dirname(_cacert)
except Exception as e:
    logger.warning(f"[launcher] SSL 证书配置失败: {e}")

# 打包后如果在 dist/ 子目录，回溯到项目根目录以共用 data/
if getattr(sys, 'frozen', False):
    _parent = os.path.dirname(BASE_DIR)
    if os.path.exists(os.path.join(_parent, "data", "sakura.db")):
        BASE_DIR = _parent

try:
    os.chdir(BASE_DIR)
except OSError as e:
    logger.warning(f"[启动] 致命错误：无法切换到工作目录 {BASE_DIR}: {e}")
    sys.exit(1)

# ─── 常量 ───
FIXED_PORTS = [8060, 8061, 8062, 8063, 8064]
HWND_FILE = os.path.join("data", "hwnd.txt")
WM_SHOW_WINDOW = 0x0400 + 1  # WM_USER + 1
LOCK_FILE = os.path.join("data", "sakura.lock")
WEATHER_NOTIFICATION_FILE = os.path.join("data", "weather_notification.json")

# ─── 窗口尺寸 ───
sw = ctypes.windll.user32.GetSystemMetrics(0)
sh = ctypes.windll.user32.GetSystemMetrics(1)
ww = min(int(sw * 0.65), 1300)
wh = min(int(sh * 0.82), 950)

# ─── 可变共享状态 ───
_tray_icon = None
_window = None
_persistent_wndproc = None
_has_winotify = None  # 延迟加载 winotify 标记