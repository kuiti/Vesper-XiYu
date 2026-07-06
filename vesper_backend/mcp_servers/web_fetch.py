"""Web Fetch MCP Server — 让 Claude Code 抓取网页内容"""
import os
import re
import hashlib
import time
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("vesper-web")

# 缓存目录
CACHE_DIR = os.path.join(os.path.dirname(__file__), ".webcache")
os.makedirs(CACHE_DIR, exist_ok=True)

# 请求头模拟浏览器
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
}

# 代理配置（可选）
PROXY = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")


def _cache_key(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def _get_cached(url: str, ttl: int = 900) -> str | None:
    """读取缓存（默认 15 分钟 TTL）"""
    key = _cache_key(url)
    path = os.path.join(CACHE_DIR, f"{key}.txt")
    if os.path.exists(path):
        age = time.time() - os.path.getmtime(path)
        if age < ttl:
            with open(path, encoding="utf-8") as f:
                return f.read()
    return None


def _set_cached(url: str, content: str):
    key = _cache_key(url)
    path = os.path.join(CACHE_DIR, f"{key}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _html_to_text(html: str) -> str:
    """HTML 转纯文本，保留结构"""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        # 移除无用标签
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript"]):
            tag.decompose()

        # 保留标题层级
        for i in range(1, 7):
            for h in soup.find_all(f"h{i}"):
                h.insert_before(f"\n{'#' * i} ")
                h.insert_after("\n")

        # 保留段落
        for p in soup.find_all("p"):
            p.insert_after("\n")

        # 保留列表
        for li in soup.find_all("li"):
            li.insert_before("\n- ")

        # 保留链接
        for a in soup.find_all("a"):
            href = a.get("href", "")
            if href and href.startswith("http"):
                a.insert_after(f" ({href})")

        text = soup.get_text()

        # 清理多余空行
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()

        return text
    except ImportError:
        # 无 BeautifulSoup 时的简易提取
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


@mcp.tool()
def fetch_web(url: str, max_length: int = 15000, use_cache: bool = True) -> str:
    """抓取网页内容并转为纯文本。

    Args:
        url: 要抓取的 URL
        max_length: 返回文本最大长度（默认 15000 字符）
        use_cache: 是否使用缓存（默认 15 分钟 TTL）
    """
    import requests

    from core.security import validate_request_url
    if not validate_request_url(url):
        return f"[拒绝] URL 未通过安全校验: {url}"

    # 检查缓存
    if use_cache:
        cached = _get_cached(url)
        if cached:
            return f"[缓存命中] {url}\n\n{cached[:max_length]}"

    try:
        resp = requests.get(
            url,
            headers=HEADERS,
            timeout=15,
            proxies={"http": PROXY, "https": PROXY} if PROXY else None,
            verify=True,
        )
        resp.raise_for_status()

        # 编码处理
        if resp.encoding and resp.encoding.lower() != "utf-8":
            resp.encoding = resp.apparent_encoding

        html = resp.text
        text = _html_to_text(html)

        # 写入缓存
        if use_cache:
            _set_cached(url, text)

        return f"[OK {resp.status_code}] {url}\n\n{text[:max_length]}"

    except requests.exceptions.Timeout:
        return f"[超时] {url} — 请求超过 15 秒"
    except requests.exceptions.ConnectionError:
        return f"[连接失败] {url} — 无法建立连接"
    except requests.exceptions.HTTPError as e:
        return f"[HTTP 错误] {url} — {e}"
    except Exception as e:
        return f"[异常] {url} — {type(e).__name__}: {e}"


@mcp.tool()
def search_web(query: str, max_results: int = 5) -> str:
    """通过 DuckDuckGo 搜索网页（无需 API Key）。

    Args:
        query: 搜索关键词
        max_results: 返回结果数量（默认 5）
    """
    import requests

    try:
        # DuckDuckGo HTML 搜索（无需 API）
        url = "https://html.duckduckgo.com/html/"
        resp = requests.post(
            url,
            data={"q": query, "b": ""},
            headers=HEADERS,
            timeout=15,
            proxies={"http": PROXY, "https": PROXY} if PROXY else None,
            verify=True,
        )
        resp.raise_for_status()

        # 提取搜索结果
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            for item in soup.select(".result")[:max_results]:
                title_el = item.select_one(".result__title a")
                snippet_el = item.select_one(".result__snippet")
                if title_el:
                    title = title_el.get_text(strip=True)
                    href = title_el.get("href", "")
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                    results.append(f"**{title}**\n{href}\n{snippet}")
            if results:
                return f"搜索: {query}\n\n" + "\n\n".join(results)
        except ImportError:
            pass

        # fallback: 提取链接
        links = re.findall(r'href="(https?://[^"]+)"', resp.text)
        unique = list(dict.fromkeys(links))[:max_results * 2]
        # 过滤掉搜索引擎自身链接
        unique = [l for l in unique if "duckduckgo" not in l][:max_results]
        return f"搜索: {query}\n\n" + "\n".join(f"- {l}" for l in unique)

    except Exception as e:
        return f"[搜索失败] {query} — {type(e).__name__}: {e}"


@mcp.tool()
def fetch_github(repo: str, path: str = "") -> str:
    """抓取 GitHub 仓库或文件内容。

    Args:
        repo: 仓库名，如 "cpacker/MemGPT"
        path: 文件路径，如 "README.md"（留空则获取仓库首页）
    """
    url = f"https://github.com/{repo}"
    if path:
        url += f"/blob/main/{path}"

    # 使用 raw.githubusercontent.com 获取纯文本
    if path:
        raw_url = f"https://raw.githubusercontent.com/{repo}/main/{path}"
    else:
        raw_url = f"https://raw.githubusercontent.com/{repo}/main/README.md"

    return fetch_web(raw_url, max_length=20000, use_cache=True)


@mcp.tool()
def clear_cache() -> str:
    """清除网页缓存"""
    count = 0
    for f in os.listdir(CACHE_DIR):
        if f.endswith(".txt"):
            os.remove(os.path.join(CACHE_DIR, f))
            count += 1
    return f"已清除 {count} 个缓存文件"


if __name__ == "__main__":
    mcp.run()
