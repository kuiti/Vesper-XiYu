# launcher/ — 佐仓启动器包
# 原 launcher.py（854行）拆分为子模块，本文件包含主流程

import sys
import os
import threading
import ctypes
import json as _json
import time as _time
import shutil as _shutil
import logging as _log

from . import _shared as _s
from ._shared import (
    BASE_DIR, FIXED_PORTS, HWND_FILE, WM_SHOW_WINDOW, LOCK_FILE,
    WEATHER_NOTIFICATION_FILE, sw, sh, ww, wh,
)

# 导出子模块公共函数（兼容旧 import）
from .lock import _check_instance_lock, _is_pid_alive, _write_instance_lock
from .process import (
    _kill_zombie_processes, _find_existing_instance, _activate_existing_window,
    _start_pipe_server, _find_free_port, start_backend,
)
from .window import (
    _read_theme, _write_hwnd, _set_titlebar_theme, _set_window_icon,
    _set_window_appid, _find_and_set_dark, _register_wnd_proc, _on_closing, _show_toast,
)
from .tray import _create_tray_icon_image, _on_tray_show, _on_tray_quit, _setup_tray
from .weather import _poll_weather_notifications

# ─── WebView2 会话缓存清理 ───
_webview_cache = os.path.join(BASE_DIR, "data", "webview2_data")
os.makedirs(_webview_cache, exist_ok=True)
_webview_default = os.path.join(_webview_cache, "EBWebView", "Default")
if os.path.exists(_webview_default):
    for _sub in ["Cache", "Code Cache", "Service Worker", "Session Storage",
                 "GPUCache", "DawnGraphiteCache", "DawnWebGPUCache",
                 "blob_storage", "IndexedDB", "shared_proto_db"]:
        try:
            _shutil.rmtree(os.path.join(_webview_default, _sub))
        except Exception:
            pass
    for _f in ["History", "History-journal", "Favicons", "Top Sites",
               "Visited Links", "Login Data", "Login Data For Account",
               "Web Data", "Web Data-journal"]:
        try:
            os.remove(os.path.join(_webview_default, _f))
        except Exception:
            pass

os.environ["WEBVIEW2_USER_DATA_FOLDER"] = _webview_cache

# ─── 读取主题 ───
_last_theme = _read_theme()

# ─── 加载页 HTML ───
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


def _ensure_geo_prefs():
    """写 WebView2 Preferences 文件预授权地理位置"""
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
        for _port in FIXED_PORTS:
            _key = f"http://127.0.0.1:{_port},*"
            if _key not in _geo:
                _geo[_key] = {"setting": 1, "last_modified": _ts}
                _granted = True
        if _granted:
            with open(_prefs_path, "w", encoding="utf-8") as _f:
                _json.dump(_prefs, _f, ensure_ascii=False)
    except Exception:
        pass


def run():
    """主流程入口（由 launcher.py 的 if __name__ 调用）"""
    global loading_html

    # 0. Windows 命名互斥体
    _MUTEX_NAME = "SakuraAI_SingleInstance_1A2B3C"
    _kernel32 = ctypes.windll.kernel32
    _mutex = _kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    if _kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        _wait_rc = _kernel32.WaitForSingleObject(_mutex, 0)
        if _wait_rc in (0, 128):
            pass
        else:
            existing_port, _ = _check_instance_lock()
            if not existing_port:
                existing_port, _ = _find_existing_instance()
            if existing_port:
                _activate_existing_window(existing_port)
            print("[启动] 已有实例在运行，退出")
            sys.exit(0)

    # 0.5 频率限制
    _launch_stamp_file = os.path.join("data", "_launch_stamp")
    try:
        if os.path.exists(_launch_stamp_file):
            with open(_launch_stamp_file, 'r') as f:
                _last_ts = float(f.read().strip() or '0')
            if _time.time() - _last_ts < 2:
                print("[启动] 启动频率过高（<2秒），跳过")
                sys.exit(0)
        with open(_launch_stamp_file, 'w') as f:
            f.write(str(_time.time()))
    except Exception:
        pass

    # 1. 找端口 → 立即出窗口
    SAKURA_PORT = _find_free_port()
    _write_instance_lock(SAKURA_PORT)
    print(f"[启动] 使用端口: {SAKURA_PORT}")
    _html = loading_html.replace('__PORT__', _json.dumps(SAKURA_PORT)).replace('__THEME__', _json.dumps(_last_theme))

    # 写 config.js
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

    # 1.5 AppUserModelID
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Sakura.Zuocang")
    except Exception:
        pass

    # 1.6 地理位置预授权
    _ensure_geo_prefs()

    # 更新 SAKURA_PORT 到 geo prefs
    _prefs_path = os.path.join(BASE_DIR, "data", "webview2_data", "EBWebView", "Default", "Preferences")
    if os.path.exists(_prefs_path):
        try:
            with open(_prefs_path, "r", encoding="utf-8") as _f:
                _prefs = _json.load(_f)
            _geo = (_prefs.setdefault("profile", {})
                   .setdefault("content_settings", {})
                   .setdefault("exceptions", {})
                   .setdefault("geolocation", {}))
            _key = f"http://127.0.0.1:{SAKURA_PORT},*"
            if _key not in _geo:
                _geo[_key] = {"setting": 1, "last_modified": str(int(_time.time() * 1000000))}
                with open(_prefs_path, "w", encoding="utf-8") as _f:
                    _json.dump(_prefs, _f, ensure_ascii=False)
                print(f"[启动] 已预授权地理位置权限（端口 {SAKURA_PORT}）")
        except Exception:
            pass

    # 2. 创建窗口
    import webview
    try:
        _s._window = webview.create_window(
            title="佐仓", html=_html, width=ww, height=wh,
            x=(sw - ww) // 2, y=(sh - wh) // 2, resizable=True, min_size=(500, 350), text_select=True
        )
        _s._window.events.closing += _on_closing
        _s._window.events.loaded += _ensure_geo_prefs
    except Exception as e:
        _log.error(f'Window start failed: {e}')
        import webbrowser
        print(f"WebView2 启动失败: {e}，回退到浏览器")
        webbrowser.open(f"http://127.0.0.1:{SAKURA_PORT}/")
        try:
            input("按 Ctrl+C 退出...")
        except (EOFError, KeyboardInterrupt):
            pass
        sys.exit(1)

    # 3. 后台：深色标题栏
    if sys.platform == "win32":
        threading.Thread(target=_find_and_set_dark, daemon=True).start()

    # 4. 后台：清理僵尸进程
    threading.Thread(target=_kill_zombie_processes, daemon=True).start()

    # 5. 后台：管道 + 后端
    _start_pipe_server(SAKURA_PORT)
    print(f"[启动] 命名管道服务器已启动 (sakura_ai_{SAKURA_PORT})")
    threading.Thread(target=start_backend, args=(SAKURA_PORT,), daemon=True).start()

    # 6. 后台：系统托盘
    threading.Thread(target=_setup_tray, daemon=True).start()

    # 7. 后台：天气通知
    threading.Thread(target=_poll_weather_notifications, daemon=True).start()

    # 8. 启动 WebView 消息循环（阻塞主线程）
    webview.start(gui="edgechromium")