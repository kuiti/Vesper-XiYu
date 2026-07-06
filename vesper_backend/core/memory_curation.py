# core/memory_curation.py — 记忆整理（CCR: Curate-Consolidate-Retrieve）
"""参考 Artemis 的 CCR 机制：每 N 轮对话自动提取重要记忆并存储。

流程：
1. Curate（提取）：每 8 轮对话，LLM 从最近对话中提取值得记住的事实
2. Consolidate（固化）：存入 facts 表，自动去重合并
3. Retrieve（检索）：搜索时高置信度记忆自动注入 prompt
"""

import json
import logging
import hashlib
from datetime import datetime
from core.db import get_conn

logger = logging.getLogger(__name__)

CURATION_INTERVAL = 8  # 每 8 轮对话执行一次提取

# 置信度衰减率：0.999 ^ days，一年后约 69%，三年后约 33%
CONFIDENCE_DECAY_RATE = 0.999
# 重要性衰减率：0.998 ^ days，一年后约 48%，用于 get_facts_context 等过滤
IMPORTANCE_DECAY_RATE = 0.998


def effective_confidence(confidence: float, updated_at: str, decay_rate: float = CONFIDENCE_DECAY_RATE) -> float:
    """计算考虑时间衰减后的有效置信度。

    不修改 DB，仅在查询时动态计算，让旧记忆随时间自然降权。
    """
    if not updated_at or confidence <= 0:
        return confidence
    try:
        updated = datetime.fromisoformat(updated_at)
        days_since = (datetime.now() - updated).days
        if days_since > 0:
            return confidence * (decay_rate ** days_since)
    except Exception:
        pass
    return confidence


def effective_importance(importance: float, created_at: str) -> float:
    """计算考虑时间衰减后的有效重要性。"""
    if not created_at:
        return importance
    try:
        created = datetime.fromisoformat(created_at)
        days_since = (datetime.now() - created).days
        if days_since > 0:
            return importance * (IMPORTANCE_DECAY_RATE ** days_since)
    except Exception:
        pass
    return importance


def batch_decay_confidence(min_confidence: float = 0.1):
    """批量衰减所有事实的置信度并持久化到 DB。

    日常检索用 effective_confidence() 动态计算即可，
    此函数只在维护/清理时调用，避免 DB 写放大。
    """
    from datetime import datetime as _dt
    now = _dt.now()
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, confidence, updated_at FROM facts WHERE confidence > ?", (min_confidence,))
        rows = cursor.fetchall()
        changed = 0
        for r in rows:
            decayed = effective_confidence(r["confidence"], r["updated_at"])
            if decayed < r["confidence"] - 0.01:
                cursor.execute("UPDATE facts SET confidence = ?, updated_at = ? WHERE id = ?",
                              (max(min_confidence, round(decayed, 4)), now.isoformat(), r["id"]))
                changed += 1
        conn.commit()
        if changed:
            logger.info(f"[记忆整理] 批量衰减 {changed} 条事实的置信度")
        return changed

CURATION_PROMPT = """从以下对话中提取值得长期记住的信息。提取维度：

1. **个人信息**（职业、年龄、城市、家庭、学校等）
2. **偏好与反感**（喜欢/不喜欢的东西、习惯、禁忌）
3. **重要事件**（经历、成就、挫折、转折点）
4. **目标与计划**（想做的事、梦想、规划）
5. **情感模式**（什么让用户开心/难过/焦虑/愤怒）
6. **沟通风格**（用户喜欢简短还是详细？正式还是随意？喜欢被怎样回应？）
7. **性格特征**（内向/外向、乐观/悲观、理性/感性等）

忽略：寒暄、临时话题、一次性询问、无长期价值的日常琐事。

每条事实必须：
1. 自包含（脱离对话上下文也能理解）
2. 对未来的陪伴有帮助
3. 用简体中文，一句话说完
4. 区分永久特征和临时状态（临时状态标注 temporality=temporary）

已有事实（避免重复，如果与已有事实矛盾请标注 contradiction=true）：
{existing}

返回严格 JSON 格式：
{{"facts": [{{"text": "事实描述", "category": "personal/preference/event/goal/emotion/style/personality", "importance": 0.0-1.0, "temporality": "permanent/temporary/event", "contradiction": false}}]}}
没有新事实时返回 {{"facts": []}}

最近对话：
{conversation}"""


def extract_facts_from_conversation(conversation_text: str, existing_text: str = "") -> list[dict]:
    """调用 LLM 从对话文本中提取值得长期记住的事实，返回标准化的事实列表。"""
    try:
        from core.llm_client import call_llm
    except Exception:
        logger.warning("[记忆整理] LLM 客户端不可用")
        return []

    prompt = CURATION_PROMPT.format(
        existing=existing_text[:500] or "无",
        conversation=conversation_text[:3000],
    )

    try:
        result = call_llm(prompt=prompt, temperature=0.2, max_tokens=500, timeout=30, json_mode=True)
    except Exception as e:
        logger.warning(f"[记忆整理] LLM 调用失败: {e}")
        return []

    if not result:
        return []

    try:
        data = json.loads(result) if isinstance(result, str) else result
        facts = data.get("facts", [])
    except (json.JSONDecodeError, AttributeError):
        logger.warning(f"[记忆整理] LLM 返回格式异常: {str(result)[:100]}")
        return []

    # 过滤和标准化
    valid = []
    for f in facts:
        text = (f.get("text") or "").strip()
        if not text or len(text) < 4:
            continue
        valid.append({
            "text": text,
            "category": f.get("category", "personal"),
            "importance": min(1.0, max(0.1, float(f.get("importance", 0.5)))),
            "temporality": f.get("temporality", "permanent"),
            "contradiction": f.get("contradiction", False),
        })
    return valid


def _save_extracted_facts(facts: list[dict], source_episode: str = ""):
    """将提取的事实存入 facts 表，通过文本前缀匹配自动去重，支持矛盾检测和合并。"""
    if not facts:
        return 0

    saved = 0
    timestamp = datetime.now().isoformat()

    for fact in facts:
        text = fact["text"]
        category = fact["category"]
        importance = fact["importance"]

        # 用文本 hash 做去重 key
        text_hash = hashlib.sha256(text.encode()).hexdigest()

        with get_conn() as conn:
            cursor = conn.cursor()

            # 检查是否已存在相似事实
            cursor.execute(
                "SELECT id, importance, confidence, extracted_at, updated_at FROM facts WHERE fact_text LIKE ? ORDER BY importance DESC LIMIT 1",
                (f"%{text[:20]}%",)
            )
            existing = cursor.fetchone()

            if existing:
                # 用有效置信度（考虑时间衰减）做决策
                existing_eff_conf = effective_confidence(
                    existing["confidence"] or 0.5,
                    existing.get("updated_at") or existing.get("extracted_at") or timestamp
                )
                if fact.get("contradiction"):
                    # 矛盾检测：仅当新事实置信度高于旧事实有效置信度时才覆盖
                    if importance >= existing_eff_conf:
                        cursor.execute(
                            "UPDATE facts SET confidence = ?, updated_at = ? WHERE id = ?",
                            (max(0.1, existing_eff_conf - 0.3), timestamp, existing["id"])
                        )
                        logger.info(f"[记忆整理] 矛盾检测: 旧事实 #{existing['id']} 降权（有效置信度={existing_eff_conf:.2f}），新增: {text[:40]}")
                        # 继续新增
                        cursor.execute(
                            "INSERT INTO facts (fact_text, category, importance, confidence, source, extracted_at, updated_at) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (text, category, importance, 0.7, f"curation:{source_episode}", timestamp, timestamp)
                        )
                        saved += 1
                    else:
                        logger.info(f"[记忆整理] 矛盾跳过: 新事实置信度({importance})低于旧事实有效置信度({existing_eff_conf:.2f})")
                else:
                    # 合并：提高重要性，但保留原有文本
                    new_imp = max(importance, existing["importance"])
                    cursor.execute(
                        "UPDATE facts SET importance = ?, confidence = ?, updated_at = ? WHERE id = ?",
                        (new_imp, min(1.0, existing_eff_conf + 0.05), timestamp, existing["id"])
                    )
                    logger.info(f"[记忆整理] 更新事实 #{existing['id']}: {text[:40]}")
            else:
                # 新增
                cursor.execute(
                    "INSERT INTO facts (fact_text, category, importance, confidence, source, extracted_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (text, category, importance, 0.7, f"curation:{source_episode}", timestamp, timestamp)
                )
                saved += 1
                logger.info(f"[记忆整理] 新增事实: {text[:40]}")

    return saved


def run_curation(conversation_history: list[dict] = None):
    """执行一轮记忆整理（对外入口）

    Args:
        conversation_history: 最近对话历史，格式 [{"role": "user/assistant", "content": "..."}]
    """
    if not conversation_history:
        logger.info("[记忆整理] 无对话历史，跳过")
        return {"extracted": 0, "saved": 0}

    # 1. 获取已有事实（避免重复）
    existing_facts = []
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT fact_text FROM facts WHERE confidence >= 0.5 ORDER BY updated_at DESC LIMIT 20")
            existing_facts = [r["fact_text"] for r in cursor.fetchall()]
    except Exception as e:
        logger.warning(f"[记忆整理] 读取已有事实失败: {e}")

    existing_text = "；".join(existing_facts[:10]) if existing_facts else ""

    # 2. 将对话格式化为文本
    conv_text = "\n".join([
        f"{'用户' if m.get('role') == 'user' else '你'}: {m['content'][:200]}"
        for m in conversation_history[-12:]  # 取最近12条
    ])

    # 3. 提取事实
    facts = extract_facts_from_conversation(conv_text, existing_text)
    if not facts:
        logger.info("[记忆整理] 未提取到新事实")
        return {"extracted": 0, "saved": 0}

    # 4. 存入数据库
    saved = _save_extracted_facts(facts)

    return {"extracted": len(facts), "saved": saved}
