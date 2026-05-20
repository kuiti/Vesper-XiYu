"""
Vesper —— 独立窗口启动器  |  v3.8.0
先开窗口显示启动进度，后端就绪后自动进入聊天界面
更新: 单实例锁、WebView2 持久化数据目录、加载页内嵌
"""
# version: 3.8.0
import sys
import os
import threading
import socket

os.chdir(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(os.getcwd(), "frontend")

# 检查是否已有实例在运行
def is_already_running():
    port_file = os.path.join("data", "port.txt")
    if os.path.exists(port_file):
        with open(port_file) as f:
            port = f.read().strip()
        if port.isdigit():
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            busy = s.connect_ex(("127.0.0.1", int(port))) == 0
            s.close()
            return busy
    return False

if is_already_running():
    sys.exit(0)

def find_free_port(start=8001, end=8010):
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return 8001

def start_backend(port):
    import uvicorn
    from main import app
    os.makedirs("data", exist_ok=True)
    with open("data/port.txt", "w") as f:
        f.write(str(port))
    with open(os.path.join(FRONTEND_DIR, "config.js"), "w", encoding="utf-8") as f:
        f.write(f"window.__SAKURA_CONFIG__ = {{ backendPort: {port} }};")
    print(f"后端端口: {port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

# 0. 设置 WebView2 持久化数据目录（记住定位权限等）
os.environ["WEBVIEW2_USER_DATA_FOLDER"] = os.path.join(os.getcwd(), "data", "webview2_data")
os.makedirs(os.environ["WEBVIEW2_USER_DATA_FOLDER"], exist_ok=True)

# 1. 选端口，启动后端
port = find_free_port()
threading.Thread(target=start_backend, args=(port,), daemon=True).start()

# 2. 生成加载页 HTML（内嵌端口号）
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
<div class="box">
<h1>Vesper</h1>
<div class="steps">
<div class="step active" id="s1"><span class="dot"></span>启动后端服务</div>
<div class="step" id="s2"><span class="dot"></span>加载模型</div>
<div class="step" id="s3"><span class="dot"></span>准备就绪</div>
</div>
<div class="loader"><div class="loader-bar" id="bar"></div></div>
<div class="msg" id="msg"></div>
</div>
<script>
var PORT = ''' + str(port) + ''';
var n=0;
function step(id,status){
  var el=document.getElementById(id);if(el){el.classList.remove("active");el.classList.add(status)}
  document.getElementById("bar").style.width=((++n)/3*100)+"%"
}
function poll(){
  fetch("http://127.0.0.1:"+PORT+"/")
    .then(function(r){return r.text()})
    .then(function(txt){
      if(txt.indexOf("Vesper")>-1||txt.indexOf("app")>-1||txt.length>200){
        step("s1","done");step("s2","active");
        setTimeout(function(){
          step("s2","done");step("s3","active");
          setTimeout(function(){
            step("s3","done");
            document.getElementById("msg").textContent="正在进入...";
            setTimeout(function(){location.href="http://127.0.0.1:"+PORT+"/"},300)
          },400)
        },600)
      }else{setTimeout(poll,500)}
    }).catch(function(){setTimeout(poll,800)})
}
setTimeout(poll,300)
</script></body></html>'''

# 3. 立即打开加载窗口
import webview
import tkinter

root = tkinter.Tk()
sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
root.destroy()

ww = min(int(sw * 0.55), 1000)
wh = min(int(sh * 0.75), 720)

window = webview.create_window(
    title="Vesper",
    html=loading_html,
    width=ww,
    height=wh,
    x=(sw - ww) // 2,
    y=(sh - wh) // 2,
    resizable=True,
    min_size=(500, 350),
    text_select=True,
)

webview.start(gui="edgechromium" if sys.platform == "win32" else None)
os._exit(0)
