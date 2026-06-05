# version: 5.0.0
"""佐仓启动入口 —— 命名管道单实例 + 系统托盘 + 后台运行"""
import sys, os, threading, ctypes, logging as _log, json as _json, time as _time, socket

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

# 开发模式下也需要 SSL 证书（覆盖所有常见 HTTP 库）
try:
    import certifi
    _cacert = certifi.where()
    os.environ['SSL_CERT_FILE'] = _cacert
    os.environ['REQUESTS_CA_BUNDLE'] = _cacert
    os.environ['CURL_CA_BUNDLE'] = _cacert
    os.environ['PIP_CERT'] = _cacert
    # httpx / huggingface_hub 也看这两个
    os.environ['SSL_CERT_DIR'] = os.path.dirname(_cacert)
except Exception:
    pass

# 打包后如果在 dist/ 子目录，回溯到项目根目录以共用 data/
if getattr(sys, 'frozen', False):
    _parent = os.path.dirname(BASE_DIR)
    if os.path.exists(os.path.join(_parent, "data", "sakura.db")):
        BASE_DIR = _parent

try:
    os.chdir(BASE_DIR)
except OSError as e:
    print(f"[启动] 致命错误：无法切换到工作目录 {BASE_DIR}: {e}")
    sys.exit(1)

# ─── 5端口固定 + HTTP健康检查单实例检测 ───
import win32pipe, win32file, pywintypes

FIXED_PORTS = [8060, 8061, 8062, 8063, 8064]
HWND_FILE = os.path.join("data", "hwnd.txt")
WM_SHOW_WINDOW = 0x0400 + 1  # WM_USER + 1


def _kill_zombie_processes():
    """启动前检查固定端口，清理僵尸进程（端口被占用但无 HTTP 响应）"""
    import urllib.request
    import subprocess
    killed = []
    for port in FIXED_PORTS:
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
        except Exception:
            pass  # 无响应，是僵尸
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
            print(f"[启动] 清理端口{port}失败: {e}")
    if killed:
        print(f"[启动] 已清理僵尸进程: {', '.join(killed)}")


def _find_existing_instance():
    """遍历5个固定端口，发HTTP健康检查，找到已运行的实例。
    返回 (port, response_text)，无实例返回 (None, None)。
    """
    import urllib.request
    for port in FIXED_PORTS:
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
            print(f"[启动] 已通过管道激活端口 {port} 的窗口")
            return
    except Exception:
        pass
    # 管道失败，回退浏览器
    import webbrowser
    webbrowser.open(f"http://127.0.0.1:{port}/")
    print(f"[启动] 浏览器打开 http://127.0.0.1:{port}/")


def _start_pipe_server(port):
    """在后台线程启动命名管道服务器（管道名包含端口号）"""
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
                    _on_tray_show(None, None)
                elif cmd == 'quit':
                    win32file.WriteFile(pipe, b'ok')
                    _on_tray_quit(None, None)
                    return
                elif cmd == 'ping':
                    resp = b'pong'
                win32file.WriteFile(pipe, resp)
            except Exception as e:
                print(f"[管道] 异常: {e}")
                _time.sleep(1)
            finally:
                if pipe:
                    try: win32file.CloseHandle(pipe)
                    except Exception: pass
    t = threading.Thread(target=_serve, daemon=True)
    t.start()
    return t


def _find_free_port():
    """在5个固定端口中找第一个空闲端口"""
    import socket
    for port in FIXED_PORTS:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("所有端口(8060-8064)均被占用")

def start_backend(port):
    import uvicorn
    print(f"[后端] 开始在端口 {port} 启动...")
    try:
        from main import app  # 延迟导入，不阻塞主线程
        print(f"[后端] main 导入成功")
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
        except Exception:
            pass
        raise

# 清理 WebView2 会话缓存（保留权限和偏好，避免地理位置授权丢失）
import shutil as _shutil
_webview_cache = os.path.join(BASE_DIR, "data", "webview2_data")
os.makedirs(_webview_cache, exist_ok=True)
_webview_default = os.path.join(_webview_cache, "EBWebView", "Default")
if os.path.exists(_webview_default):
    for _sub in ["Cache", "Code Cache", "Service Worker", "Session Storage",
                 "GPUCache", "DawnGraphiteCache", "DawnWebGPUCache",
                 "blob_storage", "IndexedDB", "shared_proto_db"]:
        try: _shutil.rmtree(os.path.join(_webview_default, _sub))
        except Exception: pass
    for _f in ["History", "History-journal", "Favicons", "Top Sites",
               "Visited Links", "Login Data", "Login Data For Account",
               "Web Data", "Web Data-journal"]:
        try: os.remove(os.path.join(_webview_default, _f))
        except Exception: pass

os.environ["WEBVIEW2_USER_DATA_FOLDER"] = _webview_cache

# 读取上次保存的主题（直接读 SQLite，不依赖后端）
def _read_theme():
    import sqlite3, json
    db_path = os.path.join(BASE_DIR, "data", "sakura.db")
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
            except Exception:
                return val.strip("'\"")
    except Exception:
        pass
    return "dark"

_last_theme = _read_theme()

# config.js 延迟到主流程中写入（需要先确定 SAKURA_PORT）

# 加载页 HTML（主题自适应）
loading_html = '''<!DOCTYPE html>
<html lang="zh"><head><meta charset="UTF-8"><style>
html,body{margin:0;padding:0;overflow:hidden;width:100%;height:100%}
*{box-sizing:border-box}
body{font-family:"Microsoft YaHei",sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;background:#0f1119;color:#e2e8f0;transition:background .6s,color .6s}
body::before{content:'';position:fixed;inset:0;pointer-events:none;z-index:0;transition:opacity .6s}

/* ═══ 中心容器 ═══ */
.box{text-align:center;position:relative;z-index:2;display:flex;flex-direction:column;align-items:center;gap:20px}

/* ═══ Logo 呼吸光晕 ═══ */
.logo-wrap{position:relative;display:inline-block}
.logo{font-size:40px;font-weight:400;letter-spacing:10px;transition:color .6s;user-select:none}
@keyframes breathe{0%,100%{filter:drop-shadow(0 0 6px var(--glow));transform:scale(1)}50%{filter:drop-shadow(0 0 24px var(--glow));transform:scale(1.03)}}
.logo-wrap{animation:breathe 2.4s ease-in-out infinite}

/* ═══ 独白文字 ═══ */
.monologue{font-size:14px;min-height:24px;transition:color .6s,opacity .4s;letter-spacing:1px}
.monologue.fade{opacity:.3}

/* ═══ 进度指示 ═══ */
.progress{margin-top:12px;width:120px;height:2px;border-radius:1px;overflow:hidden;transition:background .6s}
.progress-bar{height:100%;width:0;border-radius:1px;transition:width .5s ease,background .6s}

/* ═══ Dark 深空蓝 ═══ */
body[data-theme="dark"]{--glow:#6a9fd8;background:#0f1119;color:#e2e8f0}
body[data-theme="dark"] .logo{color:#7aafe0}
body[data-theme="dark"] .monologue{color:#7b8ca0}
body[data-theme="dark"] .progress{background:#1a2030}
body[data-theme="dark"] .progress-bar{background:#6a9fd8}
body[data-theme="dark"]::before{background-image:radial-gradient(1px 1px at 8% 15%,rgba(106,159,216,.5),transparent),radial-gradient(1px 1px at 22% 35%,rgba(106,159,216,.3),transparent),radial-gradient(1.5px 1.5px at 38% 12%,rgba(58,90,128,.4),transparent),radial-gradient(1px 1px at 52% 55%,rgba(106,159,216,.35),transparent),radial-gradient(1px 1px at 68% 25%,rgba(58,90,128,.4),transparent),radial-gradient(1.5px 1.5px at 82% 48%,rgba(106,159,216,.3),transparent),radial-gradient(1px 1px at 15% 72%,rgba(58,90,128,.35),transparent),radial-gradient(1px 1px at 45% 82%,rgba(106,159,216,.25),transparent),radial-gradient(1px 1px at 75% 68%,rgba(58,90,128,.3),transparent),radial-gradient(1.5px 1.5px at 92% 15%,rgba(106,159,216,.4),transparent);animation:drift 8s ease-in-out infinite alternate}

/* ═══ Light 暖白浅樱 ═══ */
body[data-theme="light"]{--glow:#c9717a;background:#f5f0e8;color:#3d3228}
body[data-theme="light"] .logo{color:#c9717a}
body[data-theme="light"] .monologue{color:#8c7b6e}
body[data-theme="light"] .progress{background:#d8cfc4}
body[data-theme="light"] .progress-bar{background:#c9717a}
body[data-theme="light"]::before{background-image:radial-gradient(1px 1px at 10% 20%,rgba(201,113,122,.12),transparent),radial-gradient(1.5px 1.5px at 30% 50%,rgba(201,113,122,.08),transparent),radial-gradient(1px 1px at 50% 15%,rgba(212,160,144,.15),transparent),radial-gradient(1px 1px at 70% 60%,rgba(201,113,122,.1),transparent),radial-gradient(1px 1px at 85% 30%,rgba(212,160,144,.12),transparent);animation:drift 10s ease-in-out infinite alternate}

/* ═══ Sakura 樱·暗绯 ═══ */
body[data-theme="sakura"]{--glow:#e8929b;background:#1c141a;color:#f0d8e0}
body[data-theme="sakura"] .logo{color:#e8929b}
body[data-theme="sakura"] .monologue{color:#b8959e}
body[data-theme="sakura"] .progress{background:#2d1e26}
body[data-theme="sakura"] .progress-bar{background:linear-gradient(90deg,#e8929b,#8fbc8f)}
body[data-theme="sakura"]::before{background-image:radial-gradient(2px 3px at 8% 12%,rgba(232,146,155,.45),transparent),radial-gradient(2px 2px at 18% 45%,rgba(143,188,143,.25),transparent),radial-gradient(3px 2px at 28% 8%,rgba(232,146,155,.4),transparent),radial-gradient(2px 3px at 35% 62%,rgba(232,146,155,.35),transparent),radial-gradient(2px 2px at 42% 28%,rgba(143,188,143,.2),transparent),radial-gradient(3px 2px at 55% 75%,rgba(232,146,155,.45),transparent),radial-gradient(2px 3px at 62% 18%,rgba(143,188,143,.25),transparent),radial-gradient(2px 2px at 72% 52%,rgba(232,146,155,.4),transparent),radial-gradient(3px 2px at 80% 82%,rgba(232,146,155,.35),transparent),radial-gradient(2px 3px at 88% 32%,rgba(143,188,143,.2),transparent),radial-gradient(2px 2px at 12% 85%,rgba(232,146,155,.4),transparent),radial-gradient(3px 2px at 48% 92%,rgba(143,188,143,.2),transparent);animation:sakura-drift 10s ease-in-out infinite alternate}

/* ═══ Vesper 夕语·星紫 ═══ */
body[data-theme="vesper"]{--glow:#9b8fb8;background:#13101c;color:#e0d8f0}
body[data-theme="vesper"] .logo{color:#9b8fb8}
body[data-theme="vesper"] .monologue{color:#8a7ab0}
body[data-theme="vesper"] .progress{background:#1e1a2a}
body[data-theme="vesper"] .progress-bar{background:linear-gradient(90deg,#9b8fb8,#c4b8e8)}
body[data-theme="vesper"]::before{background-image:radial-gradient(1px 1px at 5% 10%,rgba(196,184,232,.7),transparent),radial-gradient(1.5px 1.5px at 15% 48%,rgba(155,143,184,.4),transparent),radial-gradient(1px 1px at 25% 18%,rgba(196,184,232,.5),transparent),radial-gradient(2px 2px at 35% 72%,rgba(155,143,184,.55),transparent),radial-gradient(1px 1px at 45% 8%,rgba(196,184,232,.4),transparent),radial-gradient(1.5px 1.5px at 55% 42%,rgba(155,143,184,.5),transparent),radial-gradient(1px 1px at 65% 78%,rgba(196,184,232,.6),transparent),radial-gradient(1px 1px at 75% 28%,rgba(155,143,184,.3),transparent),radial-gradient(2px 2px at 85% 58%,rgba(196,184,232,.5),transparent),radial-gradient(1px 1px at 92% 88%,rgba(155,143,184,.45),transparent),radial-gradient(1.5px 1.5px at 10% 62%,rgba(196,184,232,.35),transparent),radial-gradient(1px 1px at 58% 92%,rgba(155,143,184,.4),transparent);animation:twinkle 5s ease-in-out infinite alternate}

/* ═══ 动画关键帧 ═══ */
@keyframes drift{0%{opacity:.6;transform:translateY(0)}100%{opacity:.9;transform:translateY(-4px)}}
@keyframes sakura-drift{0%{opacity:.45;transform:translateY(0)}100%{opacity:.65;transform:translateY(-6px)}}
@keyframes twinkle{0%{opacity:.5}50%{opacity:.75}100%{opacity:.6}}
</style></head><body>
<div class="box">
<div class="logo-wrap"><h1 class="logo">佐　仓</h1></div>
<div class="monologue" id="mono">嗯...等一下...</div>
<div class="progress"><div class="progress-bar" id="bar"></div></div>
</div>
<script>
var PORT=__PORT__;
var THEME=__THEME__;
document.body.setAttribute("data-theme",THEME);
if(THEME==="light"){fetch("http://127.0.0.1:"+PORT+"/api/window-theme",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({dark:false})}).catch(function(){})}

var mono=document.getElementById("mono"),bar=document.getElementById("bar");
var lines={importing:["嗯...等一下...","稍等，让我醒醒神...","正在唤醒服务..."],loading_routes:["正在翻看我们的聊天...","上次聊到哪了，我想想...","整理一下记忆..."],ready:["好了，我在。","可以了，来。","嗯，来吧。"]};
function pick(arr){return arr[Math.floor(Math.random()*arr.length)]}
var lastStage="",attempts=0,maxAttempts=300;

function fadeText(txt){mono.classList.add("fade");setTimeout(function(){mono.textContent=txt;mono.classList.remove("fade")},300)}

function poll(){
  if(++attempts>maxAttempts){mono.textContent="启动超时，请检查终端后重启";mono.style.color="#e88";return}
  fetch("http://127.0.0.1:"+PORT+"/health")
    .then(function(r){return r.json()})
    .then(function(d){
      var st=d.stage||"";
      if(st!==lastStage){lastStage=st;
        if(st==="importing"){fadeText(pick(lines.importing));bar.style.width="30%"}
        else if(st==="loading_routes"){fadeText(pick(lines.loading_routes));bar.style.width="65%"}
        else if(st==="ready"){fadeText(pick(lines.ready));bar.style.width="100%";
          setTimeout(function(){location.href="http://127.0.0.1:"+PORT+"/"},500);return}
      }
      setTimeout(poll,200)
    }).catch(function(){if(!lastStage)fadeText("正在连接...");setTimeout(poll,300)})
}
setTimeout(poll,300);
</script></body></html>'''

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

def _set_window_icon(hwnd=None):
    """设置所有本进程窗口的图标（标题栏 + 任务栏）"""
    import ctypes.wintypes as wintypes
    WM_SETICON = 0x0080
    ICON_SMALL = 0
    ICON_BIG = 1
    ico_path = os.path.join(BASE_DIR, "sakura.ico")
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
        except Exception:
            pass

def _set_window_appid(hwnd, appid):
    """在窗口上设置 AppUserModelID（让任务栏关联图标）"""
    from ctypes import wintypes
    # SHGetPropertyStoreForWindow / IPropertyStore::SetValue
    shell32 = ctypes.windll.shell32
    # PKEY_AppUserModel_ID = GUID + pid
    # We use a COM-based approach via ctypes
    IID_IPropertyStore = (0x886D8EEB, 0x8CF2, 0x4446, 0x8D, 0x02, 0xCD, 0xBA, 0x1D, 0xBD, 0xCF, 0x99)
    try:
        pps = ctypes.c_void_p()
        hr = shell32.SHGetPropertyStoreForWindow(wintypes.HWND(hwnd),
            ctypes.byref(ctypes.c_void_p(ctypes.cast(ctypes.pointer(ctypes.create_string_buffer(16)), ctypes.c_void_p).value)),
            ctypes.byref(pps))
        if hr >= 0 and pps:
            # Too complex, skip for now
            pass
    except Exception:
        pass

sw = ctypes.windll.user32.GetSystemMetrics(0)
sh = ctypes.windll.user32.GetSystemMetrics(1)
ww = min(int(sw * 0.65), 1300)
wh = min(int(sh * 0.82), 950)

# ─── 重库延迟加载（启动加速）───
_has_winotify = None

def _show_toast(title, body, duration="short"):
    """Windows 原生通知，不可用时回退到 pystray 气泡"""
    try:
        from core.db import get_config
        if not get_config("use_system_notification", False):
            return
    except Exception:
        pass
    global _has_winotify
    if _has_winotify is None:
        try:
            from winotify import Notification
            _has_winotify = True
        except ImportError:
            _has_winotify = False
    if _has_winotify:
        try:
            Notification(app_id="佐仓", title=title, msg=body, duration=duration).show()
            return
        except Exception:
            pass
    if _tray_icon:
        try:
            _tray_icon.notify(body, title)
        except Exception:
            pass

_tray_icon = None
_window = None

def _create_tray_icon_image():
    """加载 sakura.ico 作为托盘图标"""
    from PIL import Image
    ico_path = os.path.join(BASE_DIR, "sakura.ico")
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
              os.path.join("data", "port.txt"), HWND_FILE, LOCK_FILE]:
        try:
            os.remove(f)
        except OSError:
            pass
    os._exit(0)

def _setup_tray():
    """设置系统托盘"""
    global _tray_icon
    import pystray
    icon_image = _create_tray_icon_image()
    menu = pystray.Menu(
        pystray.MenuItem("显示窗口", _on_tray_show, default=True),
        pystray.MenuItem("退出", _on_tray_quit)
    )
    _tray_icon = pystray.Icon("佐仓", icon_image, "佐仓", menu)
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
                _show_toast("佐仓", "佐仓已最小化到托盘")
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
        if msg == WM_SHOW_WINDOW:
            if _window:
                _window.show()
                _window.restore()
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
                csw = mi.rcMonitor[2] - mi.rcMonitor[0]; csh = mi.rcMonitor[3] - mi.rcMonitor[1]
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
    global _persistent_wndproc
    _persistent_wndproc = new_wndproc

# ─── 文件锁单实例检测（先于端口扫描，堵住 uvicorn 未就绪的竞态窗口）───
LOCK_FILE = os.path.join("data", "sakura.lock")

def _check_instance_lock():
    """检查文件锁。返回 (port, pid) 如果已有活实例，否则 (None, None)"""
    if not os.path.exists(LOCK_FILE):
        return None, None
    try:
        with open(LOCK_FILE, "r", encoding="utf-8") as f:
            data = _json.load(f)
        pid = data.get("pid")
        port = data.get("port")
        if pid and _is_pid_alive(pid):
            return port, pid
        # 僵尸锁（进程已死），清理
        os.remove(LOCK_FILE)
    except Exception:
        try:
            os.remove(LOCK_FILE)
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
        with open(LOCK_FILE, "w", encoding="utf-8") as f:
            _json.dump({"pid": os.getpid(), "port": port}, f)
    except Exception as e:
        print(f"[启动] 写入锁文件失败: {e}")

# ─── 主流程 ───

# 0. Windows 命名互斥体（内核级原子操作，杜绝双进程）
_MUTEX_NAME = "SakuraAI_SingleInstance_1A2B3C"
_kernel32 = ctypes.windll.kernel32
_mutex = _kernel32.CreateMutexW(None, False, _MUTEX_NAME)
if _kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
    # 检查旧进程是否已死（互斥体是否被抛弃）
    _wait_rc = _kernel32.WaitForSingleObject(_mutex, 0)
    if _wait_rc in (0, 128):  # WAIT_OBJECT_0 或 WAIT_ABANDONED → 旧进程已死
        pass  # 本进程接管互斥体
    else:
        # 互斥体被活进程持有 → 找已有实例激活
        existing_port, _ = _check_instance_lock()
        if not existing_port:
            existing_port, _ = _find_existing_instance()
        if existing_port:
            _activate_existing_window(existing_port)
        print("[启动] 已有实例在运行，退出")
        sys.exit(0)

# 0.5 频率限制：距上次启动 < 2 秒则跳过
import time as _time2
_launch_stamp_file = os.path.join("data", "_launch_stamp")
try:
    if os.path.exists(_launch_stamp_file):
        with open(_launch_stamp_file, 'r') as f:
            _last_ts = float(f.read().strip() or '0')
        if _time2.time() - _last_ts < 2:
            print("[启动] 启动频率过高（<2秒），跳过")
            sys.exit(0)
    with open(_launch_stamp_file, 'w') as f:
        f.write(str(_time2.time()))
except Exception:
    pass

# 1. 快速路径：找端口 → 立即出窗口（用户先看到加载动画）
SAKURA_PORT = _find_free_port()
_write_instance_lock(SAKURA_PORT)
print(f"[启动] 使用端口: {SAKURA_PORT}")
loading_html = loading_html.replace('__PORT__', _json.dumps(SAKURA_PORT)).replace('__THEME__', _json.dumps(_last_theme))

# 写 config.js（端口确定后）
_meipass = getattr(sys, '_MEIPASS', None)
_frontend_dir = os.path.join(_meipass if _meipass else BASE_DIR, "frontend")
if os.path.isdir(_frontend_dir):
    try:
        with open(os.path.join(_frontend_dir, "config.js"), "w", encoding="utf-8") as f:
            f.write(f"window.__SAKURA_CONFIG__ = {{ backendPort: {SAKURA_PORT}, theme: \"{_last_theme}\" }};")
    except OSError as e:
        print(f"[启动] 警告：无法写入 config.js: {e}")
else:
    _frontend_dir = os.path.join(BASE_DIR, "static")

# 1.5 在创建窗口前设置 AppUserModelID（决定任务栏图标）
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Sakura.Zuocang")
except Exception:
    pass

# 1.6 在 WebView2 Preferences 中预授权地理位置，避免每次弹出系统权限对话框
def _ensure_geo_prefs():
    """写 WebView2 Preferences 文件预授权地理位置（启动时+窗口加载后各调一次，防止被覆盖）"""
    _prefs_path = os.path.join(BASE_DIR, "data", "webview2_data", "EBWebView", "Default", "Preferences")
    if not os.path.exists(_prefs_path):
        try:
            os.makedirs(os.path.dirname(_prefs_path), exist_ok=True)
            with open(_prefs_path, "w", encoding="utf-8") as _f:
                _json.dump({"profile": {"content_settings": {"exceptions": {"geolocation": {}}}}}, _f)
        except Exception:
            return
    try:
        with open(_prefs_path, "r", encoding="utf-8") as _f:
            _prefs = _json.load(_f)
        _geo = (_prefs.setdefault("profile", {})
               .setdefault("content_settings", {})
               .setdefault("exceptions", {})
               .setdefault("geolocation", {}))
        _ts = str(int(_time.time() * 1000000))
        _granted = False
        for _port in [SAKURA_PORT, 8060, 8061, 8062, 8063, 8064]:
            _key = f"http://127.0.0.1:{_port},*"
            if _key not in _geo:
                _geo[_key] = {"setting": 1, "last_modified": _ts}
                _granted = True
        if _granted:
            with open(_prefs_path, "w", encoding="utf-8") as _f:
                _json.dump(_prefs, _f, ensure_ascii=False)
            print(f"[启动] 已预授权地理位置权限（端口 {SAKURA_PORT}）")
    except Exception:
        pass

_ensure_geo_prefs()

# 2. 立即创建窗口（加载动画先出现，用户不再干等）
import webview
try:
    _window = webview.create_window(
        title="佐仓", html=loading_html, width=ww, height=wh,
        x=(sw-ww)//2, y=(sh-wh)//2, resizable=True, min_size=(500, 350), text_select=True
    )
    _window.events.closing += _on_closing
    _window.events.loaded += _ensure_geo_prefs
except Exception as e:
    _log.error(f'Window start failed: {e}')
    import webbrowser
    print(f"WebView2 启动失败: {e}，回退到浏览器")
    webbrowser.open(f"http://127.0.0.1:{SAKURA_PORT}/")
    try: input("按 Ctrl+C 退出...")
    except (EOFError, KeyboardInterrupt): pass
    sys.exit(1)

if sys.platform == "win32":
    threading.Thread(target=_find_and_set_dark, daemon=True).start()

# 3. 后台：清理僵尸进程
threading.Thread(target=_kill_zombie_processes, daemon=True).start()

# 4. 后台：启动管道 + 后端
_start_pipe_server(SAKURA_PORT)
print(f"[启动] 命名管道服务器已启动 (sakura_ai_{SAKURA_PORT})")
threading.Thread(target=start_backend, args=(SAKURA_PORT,), daemon=True).start()

# 5. 后台：系统托盘（慢，放线程不阻塞窗口）
threading.Thread(target=_setup_tray, daemon=True).start()

# 6. 后台：天气通知轮询
WEATHER_NOTIFICATION_FILE = os.path.join("data", "weather_notification.json")

def _poll_weather_notifications():
    """后台轮询天气通知文件"""
    last_check = ""
    while True:
        _time.sleep(120)
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
                        title = "佐仓 · 早安天气"
                    elif push_hour == 12:
                        title = "佐仓 · 午间天气"
                    elif push_hour == 19:
                        title = "佐仓 · 晚间天气"
                    else:
                        title = "佐仓 · 天气"

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

                    _show_toast(title, body)
                    try:
                        os.remove(WEATHER_NOTIFICATION_FILE)
                    except OSError:
                        pass
        except Exception:
            pass

threading.Thread(target=_poll_weather_notifications, daemon=True).start()

# 7. 启动 WebView 消息循环（阻塞主线程，窗口已在上方创建）
webview.start(gui="edgechromium")
