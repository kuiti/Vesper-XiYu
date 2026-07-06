# core/info_collector.py — 信息采集
"""RSS 订阅 + 新闻抓取"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def fetch_rss(url: str) -> list:
    """抓取 RSS 订阅"""
    try:
        import feedparser
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:10]:
            items.append({
                "title": entry.title,
                "link": entry.link,
                "summary": entry.summary[:200] if hasattr(entry, 'summary') else "",
                "published": entry.get("published", datetime.now().isoformat())
            })
        return items
    except Exception as e:
        logger.warning(f"[RSS] 抓取失败: {e}")
        return [{"error": str(e)}]


def fetch_news(query: str) -> list:
    """简单新闻抓取（DuckDuckGo）"""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
            return [{"title": r["title"], "body": r["body"]} for r in results]
    except Exception as e:
        logger.warning(f"[新闻] 抓取失败: {e}")
        return []
