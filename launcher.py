# version: 5.0.0
"""夕语启动入口 —— 命名管道单实例 + 系统托盘 + 后台运行"""
import sys, os, threading, ctypes, logging as _log, json as _json, time as _time

# PyInstaller 打包后 __file__ 不可靠，用可执行文件位置
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
                    print(f"[启动] 复制资源失败 {_item}: {e}")
    try:
        import certifi
        os.environ['SSL_CERT_FILE'] = certifi.where()
        os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
    except Exception as e:
        print(f"[启动] certifi SSL 设置失败: {e}")
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    os.chdir(BASE_DIR)
except OSError:
    pass

# ─── 命名管道单实例检测 ───
import win32pipe, win32file, pywintypes

PIPE_NAME = '\\\\' + '.' + '\\pipe\\' + 'vesper_ai'  # \\.\pipe\vesper_ai
HWND_FILE = os.path.join("data", "hwnd.txt")
WM_SHOW_WINDOW = 0x0400 + 1  # WM_USER + 1

def _try_activate_existing():
    """尝试连接已有实例的命名管道并发送 show 命令"""
    try:
        handle = win32file.CreateFile(
            PIPE_NAME,
            win32file.GENERIC_READ | win32file.GENERIC_WRITE,
            0, None,
            win32file.OPEN_EXISTING,
            0, None)
        win32file.WriteFile(handle, b'show')
        _, resp = win32file.ReadFile(handle, 4096)
        win32file.CloseHandle(handle)
        return resp.decode('utf-8', errors='ignore').strip() == 'ok'
    except (pywintypes.error, Exception):
        return False

def _start_pipe_server():
    """在后台线程启动命名管道服务器"""
    def _serve():
        while True:
            try:
                pipe = win32pipe.CreateNamedPipe(
                    PIPE_NAME,
                    win32pipe.PIPE_ACCESS_DUPLEX,
                    win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
                    1, 4096, 4096, 0, None)
                win32pipe.ConnectNamedPipe(pipe, None)
                _, data = win32file.ReadFile(pipe, 4096)
                cmd = data.decode('utf-8', errors='ignore').strip()
                resp = b'ok'
                if cmd == 'show':
                    _on_tray_show(None, None)
                elif cmd == 'quit':
                    win32file.WriteFile(pipe, b'ok')
                    win32file.CloseHandle(pipe)
                    _on_tray_quit(None, None)
                    return
                elif cmd == 'ping':
                    resp = b'pong'
                win32file.WriteFile(pipe, resp)
                win32file.CloseHandle(pipe)
            except Exception:
                _time.sleep(1)
    t = threading.Thread(target=_serve, daemon=True)
    t.start()
    return t

SAKURA_PORT = 8060

def start_backend(port):
    import uvicorn
    from main import app  # 延迟导入，不阻塞主线程
    os.makedirs("data", exist_ok=True)
    try:
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        server = uvicorn.Server(config)
        with open(os.path.join("data", "port.txt"), "w") as f:
            f.write(str(port))
        server.run()
    except Exception:
        raise

# 设置 WebView2 持久化
os.environ["WEBVIEW2_USER_DATA_FOLDER"] = os.path.join(BASE_DIR, "data", "webview2_data")
os.makedirs(os.environ["WEBVIEW2_USER_DATA_FOLDER"], exist_ok=True)

# 读取上次保存的主题（直接读 SQLite，不依赖后端）
def _read_theme():
    import sqlite3, json
    db_path = os.path.join(BASE_DIR, "data", "vesper.db")
    if not os.path.exists(db_path):
        return "dark"
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key = 'theme'")
        row = cursor.fetchone()
        conn.close()
        if row:
            val = row[0]
            try:
                return json.loads(val)
            except Exception:
                return val.strip("'\"")
    except Exception:
        pass
    return "dark"

_last_theme = _read_theme()

# 预写 config.js（端口固定，不需要等后端启动）
_meipass = getattr(sys, '_MEIPASS', None)
_frontend = os.path.join(_meipass if _meipass else BASE_DIR, "frontend")
if os.path.isdir(_frontend):
    with open(os.path.join(_frontend, "config.js"), "w", encoding="utf-8") as f:
        f.write(f"window.__SAKURA_CONFIG__ = {{ backendPort: {SAKURA_PORT}, theme: \"{_last_theme}\" }};")

threading.Thread(target=start_backend, args=(SAKURA_PORT,), daemon=True).start()

# 加载页 HTML（主题自适应）
loading_html = '''<!DOCTYPE html>
<html lang="zh"><head><meta charset="UTF-8"><style>
html,body{margin:0;padding:0;overflow:hidden;width:100%;height:100%}
*{box-sizing:border-box}
body{font-family:"Microsoft YaHei",sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;transition:background .5s}
.box{text-align:center;position:relative;z-index:1}
h1{font-size:36px;margin-bottom:8px;font-weight:400;letter-spacing:8px;transition:color .5s}
.subtitle{font-size:12px;margin-bottom:32px;letter-spacing:2px;transition:color .5s}
.steps{display:flex;flex-direction:column;gap:12px;align-items:center}
.step{font-size:13px;display:flex;align-items:center;gap:10px;transition:color .3s}
.dot{width:8px;height:8px;border-radius:50%;transition:all .3s}
.step.done .dot{background:#6abf6a}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(1.4)}}
.loader{margin-top:28px;width:160px;height:3px;border-radius:2px;overflow:hidden;display:inline-block;transition:background .5s}
.loader-bar{height:100%;width:0;border-radius:2px;transition:width .4s ease}
.msg{font-size:11px;margin-top:24px;transition:color .5s}

/* ─── 暗色主题 ─── */
body[data-theme="dark"]{background:#1a1418;color:#ecf0f1}
body[data-theme="dark"] h1{color:#e8929b}
body[data-theme="dark"] .subtitle,body[data-theme="dark"] .step{color:#7f6b7a}
body[data-theme="dark"] .dot{background:#2e1f28}
body[data-theme="dark"] .step.active{color:#e8929b}
body[data-theme="dark"] .step.active .dot{background:#e8929b;box-shadow:0 0 8px rgba(232,146,155,.5);animation:pulse 1.2s infinite}
body[data-theme="dark"] .step.done{color:#a8d6a8}
body[data-theme="dark"] .loader{background:#2e1f28}
body[data-theme="dark"] .loader-bar{background:#e8929b;box-shadow:0 0 6px rgba(232,146,155,.4)}
body[data-theme="dark"] .msg{color:#7f6b7a}

/* ─── 亮色主题 ─── */
body[data-theme="light"]{background:#f5f6fa;color:#333}
body[data-theme="light"] h1{color:#2b6cb0}
body[data-theme="light"] .subtitle,body[data-theme="light"] .step{color:#888}
body[data-theme="light"] .dot{background:#ddd}
body[data-theme="light"] .step.active{color:#2b6cb0}
body[data-theme="light"] .step.active .dot{background:#2b6cb0;box-shadow:0 0 8px rgba(43,108,176,.4);animation:pulse 1.2s infinite}
body[data-theme="light"] .step.done{color:#27ae60}
body[data-theme="light"] .loader{background:#ddd}
body[data-theme="light"] .loader-bar{background:#2b6cb0;box-shadow:0 0 6px rgba(43,108,176,.3)}
body[data-theme="light"] .msg{color:#999}

/* ─── 樱花粉主题 ─── */
body[data-theme="sakura"]{background:#1a1418;color:#ecf0f1}
body[data-theme="sakura"] h1{color:#e8929b}
body[data-theme="sakura"] .subtitle,body[data-theme="sakura"] .step{color:#7a6575}
body[data-theme="sakura"] .dot{background:#3d2b3a}
body[data-theme="sakura"] .step.active{color:#e8929b}
body[data-theme="sakura"] .step.active .dot{background:#e8929b;box-shadow:0 0 10px rgba(232,146,155,.6);animation:pulse 1.2s infinite}
body[data-theme="sakura"] .step.done{color:#d4a0aa}
body[data-theme="sakura"] .loader{background:#3d2b3a}
body[data-theme="sakura"] .loader-bar{background:linear-gradient(90deg,#e8929b,#f0b0b8);box-shadow:0 0 8px rgba(232,146,155,.5)}
body[data-theme="sakura"] .msg{color:#7a6575}

/* ─── 夕语主题 ─── */
body[data-theme="vesper"]{background:#12101a;color:#d0c8e0}
body[data-theme="vesper"] h1{color:#9b8fb8}
body[data-theme="vesper"] .subtitle,body[data-theme="vesper"] .step{color:#5a5070}
body[data-theme="vesper"] .dot{background:#2a2540}
body[data-theme="vesper"] .step.active{color:#9b8fb8}
body[data-theme="vesper"] .step.active .dot{background:#7c6e9a;box-shadow:0 0 10px rgba(124,110,154,.6);animation:pulse 1.2s infinite}
body[data-theme="vesper"] .step.done{color:#a0d6b4}
body[data-theme="vesper"] .loader{background:#2a2540}
body[data-theme="vesper"] .loader-bar{background:linear-gradient(90deg,#7c6e9a,#9b8fb8);box-shadow:0 0 8px rgba(124,110,154,.5)}
body[data-theme="vesper"] .msg{color:#5a5070}

/* 夕语星光 */
body[data-theme="vesper"]::before{
  content:'';position:fixed;inset:0;
  background-image:
    radial-gradient(1px 1px at 10% 20%,rgba(255,255,255,.7),transparent),
    radial-gradient(1.5px 1.5px at 25% 50%,rgba(200,180,255,.6),transparent),
    radial-gradient(1px 1px at 40% 15%,rgba(255,255,255,.5),transparent),
    radial-gradient(2px 2px at 55% 70%,rgba(180,200,255,.7),transparent),
    radial-gradient(1px 1px at 70% 35%,rgba(255,255,255,.6),transparent),
    radial-gradient(1.5px 1.5px at 85% 60%,rgba(200,180,255,.5),transparent),
    radial-gradient(1px 1px at 15% 80%,rgba(255,255,255,.4),transparent),
    radial-gradient(1px 1px at 60% 10%,rgba(180,200,255,.6),transparent),
    radial-gradient(2px 2px at 30% 90%,rgba(255,255,255,.5),transparent),
    radial-gradient(1px 1px at 90% 25%,rgba(200,180,255,.7),transparent);
  animation:twinkle 5s ease-in-out infinite alternate;pointer-events:none;z-index:0;opacity:.7
}
@keyframes twinkle{0%{opacity:.5}50%{opacity:.8}100%{opacity:.6}}
</style></head><body>
<div class="box">
<h1 id="title">佐　仓</h1>
<div class="subtitle" id="sub">正在准备你的个人助手...</div>
<div class="steps">
<div class="step active" id="s1"><span class="dot"></span>唤醒服务</div>
<div class="step" id="s2"><span class="dot"></span>整理记忆</div>
<div class="step" id="s3"><span class="dot"></span>准备就绪</div>
</div>
<div class="loader"><div class="loader-bar" id="bar"></div></div>
<div class="msg" id="msg"></div>
</div>
<script>
var PORT=__PORT__;
var THEME="__THEME__";
document.body.setAttribute("data-theme",THEME);
if(THEME==="light"){fetch("http://127.0.0.1:"+PORT+"/api/window-theme",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({dark:false})}).catch(function(){})}
var s1=document.getElementById("s1"),s2=document.getElementById("s2"),s3=document.getElementById("s3"),bar=document.getElementById("bar"),msg=document.getElementById("msg");
function done(el){el.classList.remove("active");el.classList.add("done")}
var lastStage="";
function poll(){
  fetch("http://127.0.0.1:"+PORT+"/health")
    .then(function(r){return r.json()})
    .then(function(d){
      var st=d.stage||"";
      if(st!==lastStage){lastStage=st;
        if(st==="importing"){s1.classList.add("active");bar.style.width="33%"}
        else if(st==="loading_routes"){done(s1);s2.classList.add("active");bar.style.width="66%"}
        else if(st==="ready"){done(s2);s3.classList.add("active");bar.style.width="100%";
          setTimeout(function(){done(s3);location.href="http://127.0.0.1:"+PORT+"/"},300);return}
      }
      setTimeout(poll,200)
    }).catch(function(){msg.textContent="正在连接...";setTimeout(poll,300)})
}
setTimeout(poll,200);
</script></body></html>'''
loading_html = loading_html.replace('__PORT__', str(SAKURA_PORT)).replace('__THEME__', _last_theme)

def _write_hwnd(hwnd):
    try:
        with open(HWND_FILE, "w") as f:
            f.write(str(hwnd))
    except Exception as e:
        print(f"[启动] 写入 HWND 失败: {e}")

def _set_titlebar_theme(hwnd, dark=True):
    from ctypes import wintypes
    DWMWA_USE_IMMERSIVE_DARK_MODE = 20
    try:
        val = ctypes.c_int(1 if dark else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd), DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(val), ctypes.sizeof(val))
    except Exception as e:
        print(f"[启动] 深色标题栏设置失败: {e}")

import webview
sw = ctypes.windll.user32.GetSystemMetrics(0)
sh = ctypes.windll.user32.GetSystemMetrics(1)
ww = min(int(sw * 0.55), 1000)
wh = min(int(sh * 0.75), 720)

# ─── 系统托盘 ───
import pystray
from PIL import Image

_tray_icon = None
_window = None

def _create_tray_icon_image():
    """创建托盘图标（简单的粉色圆形）"""
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill=(232, 146, 155, 255))
    draw.ellipse([16, 16, 48, 48], fill=(26, 20, 24, 255))
    return img

def _on_tray_show(icon, item):
    """显示窗口"""
    global _window
    if _window:
        _window.show()
        _window.restore()
    if os.path.exists(HWND_FILE):
        try:
            with open(HWND_FILE, "r") as f:
                hwnd = int(f.read().strip())
            if hwnd and ctypes.windll.user32.IsWindow(hwnd):
                ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

def _on_tray_quit(icon, item):
    """退出程序"""
    global _window, _tray_icon
    try:
        icon.stop()
    except Exception:
        pass
    try:
        if _window:
            _window.destroy()
    except Exception:
        pass
    for f in [os.path.join("frontend", "config.js"),
              os.path.join("data", "port.txt"), HWND_FILE]:
        try:
            os.remove(f)
        except OSError:
            pass
    os._exit(0)

def _setup_tray():
    """设置系统托盘"""
    global _tray_icon
    icon_image = _create_tray_icon_image()
    menu = pystray.Menu(
        pystray.MenuItem("显示窗口", _on_tray_show, default=True),
        pystray.MenuItem("退出", _on_tray_quit)
    )
    _tray_icon = pystray.Icon("夕语", icon_image, "夕语", menu)
    _tray_icon.run_detached()

def _on_closing():
    """窗口关闭时最小化到托盘（返回 False 阻止真正关闭）"""
    global _window
    if _window:
        _window.hide()
    if _tray_icon:
        try:
            from core.db import get_config
            if get_config("show_tray_notification", True):
                _tray_icon.notify("夕语已最小化到托盘", "夕语")
        except Exception:
            pass
    return False

def _find_and_set_dark():
    """查找窗口并设置深色标题栏"""
    found = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    def _enum(hwnd, _):
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
        if buf.value == "夕语":
            found.append(hwnd)
            return False
        return True
    for _ in range(50):
        _time.sleep(0.1)
        ctypes.windll.user32.EnumWindows(WNDENUMPROC(_enum), 0)
        if found:
            _set_titlebar_theme(found[0], True)
            _write_hwnd(found[0])
            _register_wnd_proc(found[0])
            return

def _register_wnd_proc(hwnd):
    """注册窗口消息处理，用于接收来自新实例/托盘的激活消息"""
    import ctypes.wintypes as wintypes

    GWL_WNDPROC = -4
    WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM)

    _orig_wndproc = None

    def _wnd_proc(hwnd, msg, wparam, lparam):
        nonlocal _orig_wndproc
        if msg == WM_SHOW_WINDOW:
            if _window:
                _window.show()
                _window.restore()
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            return 0
        if _orig_wndproc:
            return ctypes.windll.user32.CallWindowProcW(_orig_wndproc, hwnd, msg, wparam, lparam)
        return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    _orig_wndproc = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_WNDPROC)
    new_wndproc = WNDPROC(_wnd_proc)
    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_WNDPROC, new_wndproc)
    _wnd_proc._ref = new_wndproc

# ─── 主流程 ───

# 1. 命名管道单实例检测
if _try_activate_existing():
    print("[启动] 检测到已有实例，已激活其窗口")
    sys.exit(0)

# 2. 启动管道服务器（自己是主实例）
_start_pipe_server()
print("[启动] 命名管道服务器已启动")

# 3. 启动系统托盘
_setup_tray()

# 4. 天气通知轮询
WEATHER_NOTIFICATION_FILE = os.path.join("data", "weather_notification.json")

def _poll_weather_notifications():
    """后台轮询天气通知文件"""
    last_check = ""
    while True:
        _time.sleep(30)
        try:
            if os.path.exists(WEATHER_NOTIFICATION_FILE):
                with open(WEATHER_NOTIFICATION_FILE, "r", encoding="utf-8") as f:
                    data = _json.load(f)
                created = data.get("created_at", "")
                if created != last_check:
                    last_check = created
                    weather = data.get("weather", {})
                    city = weather.get("city", "")
                    temp = weather.get("temp", "?")
                    desc = weather.get("weather", "未知")
                    suggestion = weather.get("suggestion", "")
                    push_hour = weather.get("push_hour", 0)

                    if push_hour == 7:
                        title = "夕语 · 早安天气"
                    elif push_hour == 12:
                        title = "夕语 · 午间天气"
                    elif push_hour == 19:
                        title = "夕语 · 晚间天气"
                    else:
                        title = "夕语 · 天气"

                    body = f"{city} {desc} {temp}°C"
                    if suggestion:
                        body += f"\n{suggestion}"
                    forecasts = weather.get("forecast", [])
                    for fc in forecasts:
                        label = fc.get("label", "")
                        w = fc.get("weather", "")
                        high = fc.get("high", "?")
                        low = fc.get("low", "?")
                        body += f"\n{label}: {w} {low}~{high}°C"

                    if _tray_icon:
                        try:
                            _tray_icon.notify(body, title)
                        except Exception:
                            pass
                    try:
                        os.remove(WEATHER_NOTIFICATION_FILE)
                    except OSError:
                        pass
        except Exception:
            pass

threading.Thread(target=_poll_weather_notifications, daemon=True).start()

# 5. 创建窗口并启动
try:
    _window = webview.create_window(
        title="夕语", html=loading_html, width=ww, height=wh,
        x=(sw-ww)//2, y=(sh-wh)//2, resizable=True, min_size=(500, 350), text_select=True
    )
    _window.events.closing += _on_closing

    if sys.platform == "win32":
        threading.Thread(target=_find_and_set_dark, daemon=True).start()
        webview.start(gui="edgechromium")
    else:
        webview.start()
except Exception as e:
    _log.error(f'Window start failed: {e}')
    import webbrowser
    print(f"WebView2 启动失败: {e}，回退到浏览器")
    webbrowser.open(f"http://127.0.0.1:{SAKURA_PORT}/")
    try:
        input("按 Ctrl+C 退出...")
    except (EOFError, KeyboardInterrupt):
        pass
