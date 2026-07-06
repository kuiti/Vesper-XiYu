# core/correction_memory.py — AI 纠错记忆：不让 AI 犯错后提醒改正后再犯
"""记录 AI 犯过的具体事实错误 + 用户纠正，并在后续回复中主动避坑 + 拦截修正。

闭环：
1. detect_correction(user_msg, prev_ai_reply) 检测纠正信号 → (wrong_pattern, corrected_fact, triggers)
2. record_correction() 存入 correction_memory 表
3. get_relevant_corrections(query) 按当前话题检索相关纠错
4. apply_correction_to_reply(ai_reply, corrections) 若 AI 又犯同样错 → 直接替换

与 feedback_memory 的区别：
- feedback_memory: 行为偏好（"不要写太长"）
- correction_memory: 事实错误纠正（"我说过我喜欢面条不是米饭"）

设计权衡：
- correction_memory 表存在角色库 get_chat_conn(character_id)，per-character 隔离
- 不同角色记的纠错互不污染——对角色 A 说错的事实，只对角色 A 避坑
- 若希望"事实跨角色共享"（同一件事对所有角色都避坑），未来可加全局纠错层，目前不需要
"""

import json
import re
import logging
from datetime import datetime, timedelta
from core.db import get_chat_conn
from core.retry import silent_exc

logger = logging.getLogger(__name__)

# ─── 纠正信号模式（优先级从高到低）───
# 模式1：不是 X 是 Y / 不要 X，要 Y / 不是 X 而是 Y
_PATTERN_NOT_BUT = re.compile(
    r"(?:不是|并非|别|不要|不要说|不该说)(.{1,15}?)(?:[，,。！？\s]*是|就是|而是|要|应该|该)(.{1,20})"
)
# 模式2：我说过 X / 我跟你说过 / 我提过
_PATTERN_SAID_BEFORE = re.compile(
    r"(?:我说过|我说了|我跟你说过|我之前说过|我提过|我跟你说|告诉你)(.{2,30})"
)
# 模式3：直接指出 AI 错了
_PATTERN_AI_WRONG = re.compile(
    r"(?:你说错|你说错了|你说得不对|你记错了|你搞错|你弄错|你错了|不是这样的|纠正一下)(.{0,20})"
)
# 模式4：纠正 + 正确信息
_PATTERN_CORRECT_TO = re.compile(
    r"(?:纠正|更正|应该是|其实是|准确地说是)(.{2,30})"
)

# ─── 停用词（提取 trigger 时过滤）───
_STOP_WORDS = {
    "的", "了", "是", "我", "你", "他", "她", "它", "们", "也", "都",
    "这", "那", "这个", "那个", "什么", "怎么", "为什么", "可以", "应该",
    "知道", "觉得", "感觉", "现在", "今天", "昨天", "明天", "一下", "一下",
    "啊", "哦", "嗯", "呀", "嘛", "吧", "呢", "哎", "唉", "这", "那",
    "不是", "而是", "就是", "应该是", "其实是", "准确地说是", "纠正", "更正",
    "说过", "说了", "之前", "跟你", "告诉", "你说", "我说",
}


def _extract_keywords(text: str) -> list:
    """提取关键短语：jieba 分词 + 停用词过滤 + 长度>=2"""
    if not text:
        return []
    try:
        import jieba
        words = jieba.cut(text)
    except ImportError:
        # 降级：取连续中文/英文片段
        words = re.findall(r'[一-鿿]{2,}|[a-zA-Z]{2,}', text)
    return [w for w in words if len(w) >= 2 and w not in _STOP_WORDS]


def detect_correction(user_msg: str, prev_ai_reply: str = "") -> dict | None:
    """启发式检测用户是否在纠正 AI 的事实错误。

    Returns:
        None: 不是纠正
        {"wrong_pattern": str, "corrected_fact": str, "trigger_keywords": [str]}
    """
    if not user_msg or len(user_msg) < 3:
        return None

    # 模式1：不是 X 是 Y —— 最强信号，能提取错误模式和正确事实
    m = _PATTERN_NOT_BUT.search(user_msg)
    if m:
        wrong = m.group(1).strip()
        correct = m.group(2).strip()
        if wrong and correct and wrong != correct:
            triggers = _extract_keywords(correct) + _extract_keywords(wrong)
            return {
                "wrong_pattern": wrong,
                "corrected_fact": correct,
                "trigger_keywords": list(set(triggers))[:8],
            }

    # 模式3 + 模式4：AI 错了 + 正确是 X
    m_wrong = _PATTERN_AI_WRONG.search(user_msg)
    m_correct = _PATTERN_CORRECT_TO.search(user_msg)
    if m_wrong and m_correct:
        correct = m_correct.group(1).strip()
        if correct:
            triggers = _extract_keywords(correct)
            if prev_ai_reply:
                triggers += _extract_keywords(prev_ai_reply)
            return {
                "wrong_pattern": prev_ai_reply[:50] if prev_ai_reply else "",
                "corrected_fact": correct,
                "trigger_keywords": list(set(triggers))[:8],
            }

    # 模式2：我说过 X —— 单独出现时弱信号，需 prev_ai_reply 配合
    if prev_ai_reply and _PATTERN_SAID_BEFORE.search(user_msg):
        m_said = _PATTERN_SAID_BEFORE.search(user_msg)
        fact = m_said.group(1).strip()
        if fact:
            triggers = _extract_keywords(fact) + _extract_keywords(prev_ai_reply)
            return {
                "wrong_pattern": prev_ai_reply[:50],
                "corrected_fact": fact,
                "trigger_keywords": list(set(triggers))[:8],
            }

    return None


def record_correction(user_msg: str, ai_wrong_reply: str,
                      wrong_pattern: str, corrected_fact: str,
                      trigger_keywords: list, character_id: int = 0) -> int:
    """记录一条纠错记忆（per-character）。trigger_keywords 相同的不重复记。

    Returns: correction id，或 0 表示失败
    """
    if not corrected_fact:
        return 0
    try:
        kw_json = json.dumps(trigger_keywords or [], ensure_ascii=False)
        now = datetime.now().isoformat()
        with get_chat_conn(character_id) as conn:
            cursor = conn.cursor()
            existing = cursor.execute(
                "SELECT id, apply_count FROM correction_memory WHERE active = 1 AND trigger_keywords = ?",
                (kw_json,)
            ).fetchone()
            if existing:
                cursor.execute(
                    "UPDATE correction_memory SET corrected_fact = ?, user_message = ?, ai_wrong_reply = ?, last_applied = ? WHERE id = ?",
                    (corrected_fact, user_msg[:200], ai_wrong_reply[:200], now, existing["id"])
                )
                return existing["id"]
            cursor.execute(
                """INSERT INTO correction_memory
                   (user_message, ai_wrong_reply, wrong_pattern, corrected_fact, trigger_keywords, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_msg[:200], ai_wrong_reply[:200], wrong_pattern[:100],
                 corrected_fact, kw_json, now)
            )
            return cursor.lastrowid
    except Exception as e:
        silent_exc("record_correction", e)
        return 0


def get_relevant_corrections(query: str, top_k: int = 3, character_id: int = 0) -> list:
    """按当前话题检索相关纠错记忆（per-character）。命中 trigger_keywords 的优先返回。"""
    if not query:
        return []
    try:
        query_kws = set(_extract_keywords(query))
        if not query_kws:
            return []
        with get_chat_conn(character_id) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, wrong_pattern, corrected_fact, trigger_keywords, apply_count "
                "FROM correction_memory WHERE active = 1 ORDER BY created_at DESC LIMIT 50"
            )
            rows = cursor.fetchall()

        scored = []
        for r in rows:
            try:
                kws = set(json.loads(r["trigger_keywords"] or "[]"))
            except (json.JSONDecodeError, TypeError):
                kws = set()
            overlap = len(query_kws & kws)
            if overlap == 0:
                continue
            score = overlap + r["apply_count"] * 0.5
            scored.append((score, r))
        scored.sort(key=lambda x: -x[0])
        return [r for _, r in scored[:top_k]]
    except Exception as e:
        silent_exc("get_relevant_corrections", e)
        return []


def apply_correction_to_reply(ai_reply: str, corrections: list) -> str | None:
    """若 AI 回复包含 wrong_pattern → 直接替换为 corrected_fact。
    纯文本操作，不涉及 DB，无需 character_id。

    Returns:
        修正后的回复，或 None（无需修正）
    """
    if not ai_reply or not corrections:
        return None
    for c in corrections:
        wrong = c["wrong_pattern"]
        correct = c["corrected_fact"]
        if not wrong or len(wrong) < 2:
            continue
        if wrong in ai_reply:
            return ai_reply.replace(wrong, correct, 1)
        wrong_kws = _extract_keywords(wrong)
        if wrong_kws and all(kw in ai_reply for kw in wrong_kws[:3]):
            return f"{ai_reply}\n\n（等等，我想起你说过的——{correct}）"
    return None


def mark_applied(correction_id: int, character_id: int = 0):
    """记录纠错被引用过一次（per-character）。"""
    try:
        now = datetime.now().isoformat()
        with get_chat_conn(character_id) as conn:
            conn.cursor().execute(
                "UPDATE correction_memory SET apply_count = apply_count + 1, last_applied = ? WHERE id = ?",
                (now, correction_id)
            )
    except Exception as e:
        silent_exc("mark_applied", e)


def cleanup_old_corrections(max_days: int = 180, character_id: int = 0):
    """清理超过 max_days 且 apply_count=0 的纠错（per-character）。"""
    try:
        cutoff = (datetime.now() - timedelta(days=max_days)).isoformat()
        with get_chat_conn(character_id) as conn:
            conn.cursor().execute(
                "DELETE FROM correction_memory WHERE created_at < ? AND apply_count = 0 AND active = 1",
                (cutoff,)
            )
    except Exception as e:
        silent_exc("cleanup_old_corrections", e)
