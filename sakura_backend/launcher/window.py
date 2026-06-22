# launcher/window.py — 窗口管理：主题、图标、HWND、WndProc
import os
import sys
import ctypes
import time as _time
import threading
import sqlite3
import json
import logging
from . import _shared as _s

logger = logging.getLogger(__name__)


def _read_theme():
    """读取上次保存的主题（直接读 SQLite，不依赖后端）"""
    db_path = os.path.join(_s.BASE_DIR, "data", "sakura.db")
    if not os.path.exists(db_path):
        return "dark"
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM config WHERE key = 'theme'")
            row = cursor.fetchone()
        if row:
            val = row[0]
            try:
                return json.loads(val)
            except Exception as e:
                logger.warning(f"[launcher] 解析主题 JSON 失败: {e}")
                return val.strip("'\"")
    except Exception as e:
        logger.warning(f"[launcher] 读取主题数据库失败: {e}")
    return "dark"


def _write_hwnd(hwnd):
    try:
        with open(_s.HWND_FILE, "w") as f:
            f.write(str(hwnd))
    except Exception as e:
        logger.warning(f"[启动] 写入 HWND 失败: {e}")


def _set_titlebar_theme(hwnd, dark=True):
    from ctypes import wintypes
    DWMWA_USE_IMMERSIVE_DARK_MODE = 20
    try:
        val = ctypes.c_int(1 if dark else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd), DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(val), ctypes.sizeof(val))
    except Exception as e:
        logger.warning(f"[启动] 深色标题栏设置失败: {e}")


def _set_window_icon(hwnd=None):
    """设置所有本进程窗口的图标（标题栏 + 任务栏）"""
    import ctypes.wintypes as wintypes
    WM_SETICON = 0x0080
    ICON_SMALL = 0
    ICON_BIG = 1
    ico_path = os.path.join(_s.BASE_DIR, "sakura.ico")
    if not os.path.exists(ico_path):
        return
    pid = os.getpid()

    def _set_icon_for_hwnd(h):
        hicon_small = ctypes.windll.user32.LoadImageW(0, ico_path, 1, 16, 16, 0x00000010)
        hicon_big = ctypes.windll.user32.LoadImageW(0, ico_path, 1, 256, 256, 0x00000010)
        if hicon_small:
            ctypes.windll.user32.SendMessageW(wintypes.HWND(h), WM_SETICON, ICON_SMALL, hicon_small)
        if hicon_big:
            ctypes.windll.user32.SendMessageW(wintypes.HWND(h), WM_SETICON, ICON_BIG, hicon_big)

    if hwnd:
        _set_icon_for_hwnd(hwnd)

    # 枚举本进程所有顶层窗口
    targets = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)

    def _enum_all(h, _):
        wpid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(h, ctypes.byref(wpid))
        if wpid.value == pid and ctypes.windll.user32.IsWindowVisible(h):
            targets.append(h)
        return True

    ctypes.windll.user32.EnumWindows(WNDENUMPROC(_enum_all), 0)
    for h in targets:
        _set_icon_for_hwnd(h)
        # 在窗口上直接设置 AppUserModelID（任务栏图标关联）
        try:
            _set_window_appid(h, "Sakura.Zuocang")
        except Exception as e:
            logger.warning(f"[launcher] 设置窗口 AppUserModelID 失败: {e}")


def _set_window_appid(hwnd, appid):
    """在窗口上设置 AppUserModelID（让任务栏关联图标）"""
    from ctypes import wintypes
    shell32 = ctypes.windll.shell32
    IID_IPropertyStore = (0x886D8EEB, 0x8CF2, 0x4446, 0x8D, 0x02, 0xCD, 0xBA, 0x1D, 0xBD, 0xCF, 0x99)
    try:
        pps = ctypes.c_void_p()
        hr = shell32.SHGetPropertyStoreForWindow(wintypes.HWND(hwnd),
            ctypes.byref(ctypes.c_void_p(ctypes.cast(ctypes.pointer(ctypes.create_string_buffer(16)), ctypes.c_void_p).value)),
            ctypes.byref(pps))
        if hr >= 0 and pps:
            # Too complex, skip for now
            pass
    except Exception as e:
        logger.warning(f"[launcher] 设置窗口属性商店失败: {e}")


def _find_and_set_dark():
    """查找窗口并设置深色标题栏"""
    found = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)

    def _enum(hwnd, _):
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
        if buf.value == "佐仓":
            found.append(hwnd)
            return False
        return True

    for _ in range(50):
        _time.sleep(0.1)
        ctypes.windll.user32.EnumWindows(WNDENUMPROC(_enum), 0)
        if found:
            _set_window_icon(found[0])
            _set_titlebar_theme(found[0], True)
            _write_hwnd(found[0])
            _register_wnd_proc(found[0])
            # 延迟重设图标（WebView2 初始化会重置）
            def _reapply_icon():
                for delay in [2, 5]:
                    _time.sleep(delay)
                    _set_window_icon(found[0])
            threading.Thread(target=_reapply_icon, daemon=True).start()
            return


def _register_wnd_proc(hwnd):
    """注册窗口消息处理，用于接收来自新实例/托盘的激活消息"""
    import ctypes.wintypes as wintypes

    GWLP_WNDPROC = -4 if ctypes.sizeof(ctypes.c_void_p) == 4 else -6
    WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM)

    _orig_wndproc = None
    _was_maxed = False

    def _wnd_proc(hwnd, msg, wparam, lparam):
        nonlocal _orig_wndproc, _was_maxed
        if msg == _s.WM_SHOW_WINDOW:
            if _s._window:
                _s._window.show()
                _s._window.restore()
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            return 0
        if msg == 0x0005:  # WM_SIZE
            if wparam == 2:  # SIZE_MAXIMIZED
                _was_maxed = True
            elif wparam == 0 and _was_maxed:  # SIZE_RESTORED from maximized
                _was_maxed = False
                # 用窗口所在显示器的尺寸，而非主屏
                MONITOR_DEFAULTTONEAREST = 2
                hmon = ctypes.windll.user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)

                class MONITORINFO(ctypes.Structure):
                    _fields_ = [('cbSize', ctypes.c_ulong), ('rcMonitor', ctypes.c_long * 4), ('rcWork', ctypes.c_long * 4), ('dwFlags', ctypes.c_ulong)]

                mi = MONITORINFO()
                mi.cbSize = ctypes.sizeof(MONITORINFO)
                ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(mi))
                csw = mi.rcMonitor[2] - mi.rcMonitor[0]
                csh = mi.rcMonitor[3] - mi.rcMonitor[1]
                tw = min(int(csw * 0.65), 1300)
                th = min(int(csh * 0.82), 950)
                tx = mi.rcMonitor[0] + (csw - tw) // 2
                ty = mi.rcMonitor[1] + (csh - th) // 2
                ctypes.windll.user32.SetWindowPos(hwnd, 0, tx, ty, tw, th, 0x0004)
                return 0
        if _orig_wndproc:
            return ctypes.windll.user32.CallWindowProcW(_orig_wndproc, hwnd, msg, wparam, lparam)
        return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    _orig_wndproc = ctypes.windll.user32.GetWindowLongPtrW(hwnd, GWLP_WNDPROC)
    new_wndproc = WNDPROC(_wnd_proc)
    ctypes.windll.user32.SetWindowLongPtrW(hwnd, GWLP_WNDPROC, new_wndproc)
    _s._persistent_wndproc = new_wndproc


def _on_closing():
    """窗口关闭时最小化到托盘（返回 False 阻止真正关闭）"""
    if _s._window:
        _s._window.hide()
    if _s._tray_icon:
        try:
            from core.db import get_config
            if get_config("show_tray_notification", True):
                _show_toast("佐仓", "佐仓已最小化到托盘")
        except Exception as e:
            logger.warning(f"[launcher] 显示托盘通知失败: {e}")
    return False


def _show_toast(title, body, duration="short"):
    """Windows 原生通知，不可用时回退到 pystray 气泡"""
    try:
        from core.db import get_config
        if not get_config("use_system_notification", False):
            return
    except Exception as e:
        logger.warning(f"[launcher] 读取通知配置失败: {e}")
    if _s._has_winotify is None:
        try:
            from winotify import Notification
            _s._has_winotify = True
        except ImportError:
            _s._has_winotify = False
    if _s._has_winotify:
        try:
            from winotify import Notification
            Notification(app_id="佐仓", title=title, msg=body, duration=duration).show()
            return
        except Exception as e:
            logger.warning(f"[launcher] winotify 通知发送失败: {e}")
    if _s._tray_icon:
        try:
            _s._tray_icon.notify(body, title)
        except Exception as e:
            logger.warning(f"[launcher] pystray 通知发送失败: {e}")