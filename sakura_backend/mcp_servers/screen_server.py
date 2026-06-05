"""Screen Capture MCP Server — 让 Claude Code 截取和分析屏幕"""
import os
import tempfile
import time
from mcp.server.fastmcp import FastMCP
import mss
import mss.tools

mcp = FastMCP("sakura-screen")

SCREENSHOT_DIR = os.environ.get("SCREENSHOT_DIR", os.path.join(tempfile.gettempdir(), "claude_screenshots"))
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def _capture(monitor: int = 0, region: tuple = None) -> str:
    """截屏并保存为 PNG，返回文件路径"""
    import uuid as _uuid
    timestamp = int(time.time() * 1000)
    filepath = os.path.join(SCREENSHOT_DIR, f"screenshot_{timestamp}_{_uuid.uuid4().hex[:6]}.png")

    with mss.MSS() as sct:
        if region:
            mon = {"left": region[0], "top": region[1],
                   "width": region[2], "height": region[3]}
        elif 0 <= monitor < len(sct.monitors):
            mon = sct.monitors[monitor]
        else:
            mon = sct.monitors[0]

        img = sct.grab(mon)
        mss.tools.to_png(img.rgb, img.size, output=filepath)

    return filepath


@mcp.tool()
def screenshot() -> str:
    """截取主显示器的完整屏幕截图。返回 PNG 文件路径。Claude 可用 Read 工具查看该路径。"""
    filepath = _capture(monitor=1)
    return f"截图已保存: {filepath}\n{_screen_info(filepath)}"


@mcp.tool()
def screenshot_all() -> str:
    """截取所有显示器（虚拟桌面）的完整截图。返回 PNG 文件路径。"""
    filepath = _capture(monitor=0)
    return f"截图已保存: {filepath}\n{_screen_info(filepath)}"


@mcp.tool()
def screenshot_region(left: int, top: int, width: int, height: int) -> str:
    """截取屏幕指定区域。left/top=左上角坐标, width/height=区域宽高。返回 PNG 文件路径。"""
    if width <= 0 or height <= 0:
        return "错误：width 和 height 必须大于 0"
    filepath = _capture(region=(left, top, width, height))
    return f"截图已保存: {filepath}\n{_screen_info(filepath)}"


@mcp.tool()
def list_screens() -> str:
    """列出所有显示器信息（编号、尺寸、位置）"""
    with mss.MSS() as sct:
        lines = []
        for i, m in enumerate(sct.monitors):
            lines.append(f"显示器 {i}: {m['width']}x{m['height']} @ ({m['left']}, {m['top']})")
        return "\n".join(lines)


def _screen_info(filepath: str) -> str:
    size_kb = os.path.getsize(filepath) // 1024
    return f"文件大小: {size_kb} KB"


if __name__ == "__main__":
    mcp.run()
