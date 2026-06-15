# launcher/tray.py — 系统托盘
import os
import sys
import ctypes
from . import _shared as _s


def _create_tray_icon_image():
    """加载 sakura.ico 作为托盘图标"""
    from PIL import Image
    ico_path = os.path.join(_s.BASE_DIR, "sakura.ico")
    if os.path.exists(ico_path):
        return Image.open(ico_path)
    # 回退：简单粉色圆形
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill=(232, 146, 155, 255))
    draw.ellipse([16, 16, 48, 48], fill=(26, 20, 24, 255))
    return img


def _on_tray_show(icon, item):
    """显示窗口"""
    if _s._window:
        _s._window.show()
        _s._window.restore()
    if os.path.exists(_s.HWND_FILE):
        try:
            with open(_s.HWND_FILE, "r") as f:
                hwnd = int(f.read().strip())
            if hwnd and ctypes.windll.user32.IsWindow(hwnd):
                ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass


def _on_tray_quit(icon, item):
    """退出程序"""
    try:
        icon.stop()
    except Exception:
        pass
    try:
        if _s._window:
            _s._window.destroy()
    except Exception:
        pass
    for f in [os.path.join("frontend", "config.js"),
              os.path.join("data", "port.txt"), _s.HWND_FILE, _s.LOCK_FILE]:
        try:
            os.remove(f)
        except OSError:
            pass
    sys.exit(0)


def _setup_tray():
    """设置系统托盘"""
    import pystray
    icon_image = _create_tray_icon_image()
    menu = pystray.Menu(
        pystray.MenuItem("显示窗口", _on_tray_show, default=True),
        pystray.MenuItem("退出", _on_tray_quit)
    )
    _s._tray_icon = pystray.Icon("佐仓", icon_image, "佐仓", menu)
    _s._tray_icon.run_detached()