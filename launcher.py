# version: 3.9.0
"""Vesper启动入口 —— 兼容开发模式和 PyInstaller 打包模式"""
import sys, os, threading, socket, tkinter, atexit, ctypes

# PyInstaller 打包后 __file__ 不可靠，用可执行文件位置
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    try:
        import certifi
        os.environ['SSL_CERT_FILE'] = certifi.where()
        os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
    except Exception:
        pass
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    os.chdir(BASE_DIR)
except OSError:
    pass

# ─── 单实例锁（Windows 命名互斥体） ───
_mutex_name = "Global\\VesperAI_SingleInstance_" + os.path.abspath(BASE_DIR).replace("\\", "_").replace(":", "")
try:
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, _mutex_name)
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        sys.exit(0)
except Exception:
    pass  # 非 Windows 或权限不足，跳过单实例检查

def allocate_port():
    """由 OS 分配空闲端口（无竞态）"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def start_backend(port):
    import uvicorn
    from main import app
    os.makedirs("data", exist_ok=True)
    frontend = os.path.join(BASE_DIR, "frontend")
    if os.path.isdir(frontend):
        with open(os.path.join(frontend, "config.js"), "w", encoding="utf-8") as f:
            f.write(f"window.__VESPER_CONFIG__ = {{ backendPort: {port} }};")
    # port.txt 在绑定成功后写入
    try:
        _port_written = False
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        server = uvicorn.Server(config)
        # 尽早写入 port，供健康检查验证
        with open(os.path.join("data", "port.txt"), "w") as f:
            f.write(str(port))
        _port_written = True
        server.run()
    except Exception:
        if not _port_written and os.path.exists(os.path.join("data", "port.txt")):
            os.remove(os.path.join("data", "port.txt"))
        raise

# 退出时清理
def _cleanup():
    try: os.remove(os.path.join("data", "config.js"))
    except: pass
    try: os.remove(os.path.join("data", "port.txt"))
    except: pass
atexit.register(_cleanup)

# 设置 WebView2 持久化
os.environ["WEBVIEW2_USER_DATA_FOLDER"] = os.path.join(BASE_DIR, "data", "webview2_data")
os.makedirs(os.environ["WEBVIEW2_USER_DATA_FOLDER"], exist_ok=True)

port = allocate_port()
# 在后台线程启动前导入 main，避免导入错误被静默吞噬
try:
    from main import app
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
threading.Thread(target=start_backend, args=(port,), daemon=True).start()

# 加载页 HTML
loading_html = '''<!DOCTYPE html>
<html lang="zh"><head><meta charset="UTF-8"><style>
html,body{margin:0;padding:0;overflow:hidden;width:100%;height:100%}
*{box-sizing:border-box}
body{font-family:"Microsoft YaHei",sans-serif;background:#0d1117;color:#ecf0f1;display:flex;justify-content:center;align-items:center;height:100vh}
.box{text-align:center}
h1{font-size:28px;color:#5390d4;margin-bottom:24px;font-weight:400;letter-spacing:4px}
.steps{display:flex;flex-direction:column;gap:10px;align-items:center}
.step{font-size:13px;color:#7f8c8d;display:flex;align-items:center;gap:8px;transition:color .3s}
.dot{width:8px;height:8px;border-radius:50%;background:#2c3e50;transition:background .3s}
.step.done{color:#4caf50}.step.done .dot{background:#4caf50}
.step.active{color:#5390d4}.step.active .dot{background:#5390d4;animation:pulse .8s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.loader{margin-top:24px;width:140px;height:3px;background:#2c3e50;border-radius:2px;overflow:hidden;display:inline-block}
.loader-bar{height:100%;width:0;background:#5390d4;border-radius:2px;transition:width .4s ease}
.msg{font-size:11px;color:#555;margin-top:20px}
</style></head><body>
<div class="box"><h1>Vesper</h1>
<div class="steps">
<div class="step active" id="s1"><span class="dot"></span>启动后端服务</div>
<div class="step" id="s2"><span class="dot"></span>加载模型</div>
<div class="step" id="s3"><span class="dot"></span>准备就绪</div>
</div>
<div class="loader"><div class="loader-bar" id="bar"></div></div>
<div class="msg" id="msg"></div>
</div>
<script>
var PORT=''' + str(port) + ''';
var n=0;
function step(id,status){
  var el=document.getElementById(id);if(el){el.classList.remove("active");el.classList.add(status)}
  document.getElementById("bar").style.width=((++n)/3*100)+"%"
}
function poll(){
  fetch("http://127.0.0.1:"+PORT+"/")
    .then(function(r){return r.text()})
    .then(function(txt){
      if(txt.indexOf("app")>-1||txt.length>200){
        step("s1","done");step("s2","active");
        setTimeout(function(){step("s2","done");step("s3","active");
          setTimeout(function(){step("s3","done");document.getElementById("msg").textContent="...";
            setTimeout(function(){location.href="http://127.0.0.1:"+PORT+"/"},300)},400)},600)
      }else{setTimeout(poll,500)}
    }).catch(function(){setTimeout(poll,800)})
}
setTimeout(poll,300);
fetch("http://127.0.0.1:"+PORT+"/api/window-theme",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({dark:true})}).catch(function(){});
</script></body></html>'''

HWND_FILE = os.path.join("data", "hwnd.txt")


def _write_hwnd(hwnd):
    try:
        with open(HWND_FILE, "w") as f:
            f.write(str(hwnd))
    except Exception:
        pass


def _set_titlebar_theme(hwnd, dark=True):
    import ctypes
    from ctypes import wintypes
    DWMWA_USE_IMMERSIVE_DARK_MODE = 20
    try:
        val = ctypes.c_int(1 if dark else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd), DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(val), ctypes.sizeof(val))
    except Exception:
        pass


import webview
root = tkinter.Tk()
root.withdraw()  # 禁止闪窗
sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
root.destroy()

ww = min(int(sw * 0.55), 1000)
wh = min(int(sh * 0.75), 720)

try:
    webview.create_window(
        title="Vesper", html=loading_html, width=ww, height=wh,
        x=(sw-ww)//2, y=(sh-wh)//2, resizable=True, min_size=(500, 350), text_select=True
    )
    if sys.platform == "win32":
        # Start a background thread to apply dark title bar as soon as window appears
        import time as _time, threading as _th
        def _find_and_set_dark():
            for _ in range(50):  # try for ~5 seconds
                _time.sleep(0.1)
                hwnd = ctypes.windll.user32.FindWindowW(None, "Vesper")
                if hwnd:
                    _set_titlebar_theme(hwnd, True)
                    _write_hwnd(hwnd)
                    return
        _th.Thread(target=_find_and_set_dark, daemon=True).start()
        webview.start(gui="edgechromium")
    else:
        webview.start()
except Exception as e:
    # WebView2 运行时未安装 → 回退到系统浏览器
    import webbrowser
    print(f"WebView2 启动失败: {e}，回退到浏览器")
    webbrowser.open(f"http://127.0.0.1:{port}/")
    try:
        input("按 Ctrl+C 退出...")
    except (EOFError, KeyboardInterrupt):
        pass
sys.exit(0)
