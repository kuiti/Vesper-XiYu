# core/mention_tracker.py — 跨组件提及计数中枢
"""记录用户反复提及的关键短语，输出权重 0-1，供检索/巩固/摘要复用。

闭环：
1. record_mention(text) → jieba 分词提取关键短语 → count+1, weight=log 归一化
2. get_mention_weight(phrase) → 返回当前权重 0-1
3. get_top_mentions(n) → 返回权重最高的 N 个
4. decay_all() → 每日衰减 weight *= 0.95（防 3 年后全饱和）

权重公式：weight = min(1.0, log(count+1) / log(6))
- count=1 → 0.39（提过一次，弱信号）
- count=3 → 0.78（强调过，强信号）
- count=5+ → 1.0（上限）

与 correction_memory 的区别：
- correction_memory: 显式纠正（"不是X是Y"）
- mention_tracker: 隐式频次（提了 N 次 → 重要）

设计权衡：
- mention_weights 表存在角色库 get_chat_conn(character_id)，per-character 隔离
- 不同角色的 mention 互不污染——对角色 A 反复说"面条"不会 boost 角色 B 的检索
- decay_all / cleanup_low_weight 由 scheduler 按角色遍历调用
"""

import math
import logging
from datetime import datetime, timedelta
from core.db import get_chat_conn
from core.retry import silent_exc

logger = logging.getLogger(__name__)

# ─── 停用词（提取 mention 时过滤）───
_STOP_WORDS = {
    "的", "了", "是", "我", "你", "他", "她", "它", "们", "也", "都",
    "这", "那", "这个", "那个", "什么", "怎么", "为什么", "可以", "应该",
    "知道", "觉得", "感觉", "现在", "今天", "昨天", "明天", "一下",
    "啊", "哦", "嗯", "呀", "嘛", "吧", "呢", "哎", "唉",
    "不是", "就是", "而是", "就是", "可能", "也许", "或者", "但是",
    "因为", "所以", "如果", "虽然", "不过", "然后", "其实", "真的",
    "一个", "一些", "有点", "非常", "特别", "超级", "比较", "十分",
}

# 单短语最大长度（避免 jieba 切出超长片段）
_MAX_PHRASE_LEN = 8
# 触发权重的最小计数（少于 2 次的不算）
_MIN_COUNT_FOR_WEIGHT = 2
# 单条消息最多记录的短语数（防长消息刷屏）
_MAX_PHRASES_PER_MSG = 8


def _extract_phrases(text: str) -> list:
    """提取关键短语：jieba 分词 + 停用词过滤 + 长度 2-8"""
    if not text:
        return []
    try:
        import jieba
        words = jieba.cut(text)
    except ImportError:
        import re
        words = re.findall(r'[一-鿿]{2,8}|[a-zA-Z]{2,}', text)
    phrases = []
    for w in words:
        w = w.strip()
        if not w or len(w) < 2 or len(w) > _MAX_PHRASE_LEN:
            continue
        if w in _STOP_WORDS:
            continue
        # 过滤纯数字
        if w.isdigit():
            continue
        phrases.append(w)
    # 去重保序，限制数量
    seen = set()
    out = []
    for p in phrases:
        if p not in seen:
            seen.add(p)
            out.append(p)
        if len(out) >= _MAX_PHRASES_PER_MSG:
            break
    return out


def _calc_weight(count: int) -> float:
    """count → weight 归一化：log(count+1)/log(6)，上限 1.0"""
    if count < _MIN_COUNT_FOR_WEIGHT:
        return 0.0
    return min(1.0, math.log(count + 1) / math.log(6))


def record_mention(text: str, character_id: int = 0):
    """记录一条用户消息中的所有关键短语提及（per-character）。"""
    if not text or len(text) < 3:
        return
    phrases = _extract_phrases(text)
    if not phrases:
        return
    now = datetime.now().isoformat()
    try:
        with get_chat_conn(character_id) as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(phrases))
            cursor.execute(
                f"SELECT phrase, count FROM mention_weights WHERE phrase IN ({placeholders})",
                phrases
            )
            existing = {r["phrase"]: r["count"] for r in cursor.fetchall()}
            for p in phrases:
                if p in existing:
                    new_count = existing[p] + 1
                    cursor.execute(
                        "UPDATE mention_weights SET count = ?, weight = ?, last_mentioned = ? WHERE phrase = ?",
                        (new_count, _calc_weight(new_count), now, p)
                    )
                else:
                    cursor.execute(
                        "INSERT INTO mention_weights (phrase, count, weight, first_mentioned, last_mentioned) VALUES (?, 1, ?, ?, ?)",
                        (p, _calc_weight(1), now, now)
                    )
    except Exception as e:
        silent_exc("record_mention", e)


def get_mention_weight(phrase: str, character_id: int = 0) -> float:
    """获取单个短语的当前权重 0-1（per-character）。"""
    if not phrase:
        return 0.0
    try:
        with get_chat_conn(character_id) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT weight FROM mention_weights WHERE phrase = ?", (phrase,))
            row = cursor.fetchone()
            return row["weight"] if row else 0.0
    except Exception:
        return 0.0


def get_mention_weights(phrases: list, character_id: int = 0) -> dict:
    """批量获取权重，返回 {phrase: weight}（per-character）。"""
    if not phrases:
        return {}
    try:
        with get_chat_conn(character_id) as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(phrases))
            cursor.execute(
                f"SELECT phrase, weight FROM mention_weights WHERE phrase IN ({placeholders})",
                phrases
            )
            return {r["phrase"]: r["weight"] for r in cursor.fetchall()}
    except Exception:
        return {}


def get_top_mentions(n: int = 10, min_weight: float = 0.3, character_id: int = 0) -> list:
    """返回权重最高的 N 个短语（per-character）。"""
    try:
        with get_chat_conn(character_id) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT phrase, count, weight, last_mentioned FROM mention_weights WHERE weight >= ? ORDER BY weight DESC LIMIT ?",
                (min_weight, n)
            )
            return [dict(r) for r in cursor.fetchall()]
    except Exception:
        return []


def decay_all(character_id: int = 0):
    """每日衰减：weight *= 0.95，count 不变（per-character）。
    防止 3 年后所有短语都饱和到 1.0。
    """
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        with get_chat_conn(character_id) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT phrase, weight FROM mention_weights WHERE (decayed_at IS NULL OR decayed_at != ?) AND weight > 0",
                (today,)
            )
            rows = cursor.fetchall()
            if not rows:
                return 0
            for r in rows:
                new_w = r["weight"] * 0.95
                cursor.execute(
                    "UPDATE mention_weights SET weight = ?, decayed_at = ? WHERE phrase = ?",
                    (new_w, today, r["phrase"])
                )
        return len(rows)
    except Exception as e:
        silent_exc("decay_all", e)
        return 0


def cleanup_low_weight(max_days: int = 90, character_id: int = 0):
    """清理超过 max_days 且 weight<0.1 的短语（per-character）。"""
    try:
        cutoff = (datetime.now() - timedelta(days=max_days)).isoformat()
        with get_chat_conn(character_id) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM mention_weights WHERE weight < 0.1 AND last_mentioned < ?",
                (cutoff,)
            )
            return cursor.rowcount
    except Exception as e:
        silent_exc("cleanup_low_weight", e)
        return 0
