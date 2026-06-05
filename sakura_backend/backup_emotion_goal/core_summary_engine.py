# core/summary_engine.py  |  三级生命周期摘要引擎
import json
import random
import threading
import requests
import re
import traceback
from datetime import datetime
from core import db
from core.db import get_config

# ========== 常量 ==========
TIER_THRESHOLDS = {1: 10, 2: 50, 3: 100}
TIER_BASE_LIFESPAN = {1: (3, 7), 2: (7, 30), 3: (30, 180)}

# 提及增加档位（占基础寿命中值的比例）
MENTION_BOOST_TIERS = [0.4, 0.6, 0.8, 1.0, 1.2]

# 重要性离散映射
IMPORTANCE_MAP = {"低": 0.2, "中": 0.5, "高": 0.8, "low": 0.2, "medium": 0.5, "high": 0.8}

_summary_lock = threading.Lock()


# ========== 工具函数 ==========
def cosine_sim(a, b):
    """纯 Python 余弦相似度，不依赖 numpy"""
    dot = sum(x * y for x, y in zip(a, b))
    norm = (sum(x * x for x in a) ** 0.5) * (sum(x * x for x in b) ** 0.5)
    return dot / norm if norm else 0.0


def calculate_lifespan(level, importance):
    lo, hi = TIER_BASE_LIFESPAN[level]
    base = random.uniform(lo, hi)
    return base * (0.5 + importance) * random.uniform(0.8, 1.2)


def calculate_mention_boost(level, mention_count):
    lo, hi = TIER_BASE_LIFESPAN[level]
    midpoint = (lo + hi) / 2
    base_boost = midpoint * 0.25
    daily_cap = midpoint * 0.4
    tier_index = max(0, min(mention_count, 5) - 1)  # 0-4
    boost = base_boost * MENTION_BOOST_TIERS[tier_index]
    return min(boost, daily_cap)


def calculate_daily_cap(level):
    lo, hi = TIER_BASE_LIFESPAN[level]
    return ((lo + hi) / 2) * 0.4


def determine_tier(msg_count):
    """返回需要触发的级别列表"""
    tiers = []
    for level, threshold in TIER_THRESHOLDS.items():
        if msg_count % threshold == 0:
            last = db.get_last_trigger_at(level)
            if msg_count > last:
                tiers.append(level)
    return tiers


# ========== 话题关联度检测 ==========
def check_topic_relevance(user_message):
    """高级摘要的话题关联度检测（向量相似度）"""
    try:
        from core.vector_store import search_similar, is_model_ready
    except ImportError:
        return True
    if not is_model_ready():
        return True
    results = search_similar(user_message, top_k=5)
    if not results:
        return True  # 向量库无数据时保守允许生成
    avg_distance = sum(d for _, d in results) / len(results)
    return avg_distance <= 0.8


# ========== 提及检测 ==========
def check_summary_mentions(user_message):
    """返回被提及的摘要列表"""
    active = db.get_active_tiered_summaries()
    if not active:
        return []

    mentioned = []
    keyword_hits = []

    # 第一步：key_points 子串匹配（粗筛）
    for s in active:
        kps = s.get("key_points", [])
        if not kps:
            # key_points 为空时回退：用摘要文本前50字匹配
            if len(s["summary"]) >= 4 and s["summary"][:50] in user_message:
                keyword_hits.append(s)
            continue
        for kp in kps:
            if len(kp) >= 2 and kp in user_message:
                keyword_hits.append(s)
                break

    # 第二步：向量余弦相似度（精筛）
    try:
        from core.vector_store import is_model_ready, get_embedding_model
        model_ready = is_model_ready()
    except ImportError:
        model_ready = False

    if model_ready and keyword_hits:
        model = get_embedding_model()
        msg_emb = model.encode(user_message).tolist()
        for s in keyword_hits:
            sum_emb = model.encode(s["summary"]).tolist()
            if cosine_sim(msg_emb, sum_emb) > 0.75:
                mentioned.append(s)
    elif keyword_hits:
        mentioned = keyword_hits

    return mentioned


def process_mentions(user_message):
    """检测提及并增加寿命"""
    mentioned = check_summary_mentions(user_message)
    for s in mentioned:
        cap = calculate_daily_cap(s["level"])
        if s["daily_boost"] >= cap:
            continue
        boost = calculate_mention_boost(s["level"], s["mention_count"] + 1)
        actual_boost = min(boost, cap - s["daily_boost"])
        if actual_boost > 0:
            db.increment_mention(s["id"], actual_boost)
            s["daily_boost"] += actual_boost  # 同步更新内存快照


# ========== 摘要生成 ==========
def _format_messages(msgs):
    return "\n".join([f"{m['role']}: {m['content']}" for m in msgs])


def generate_summary_for_tier(level, messages, existing_summaries=None):
    """调 DeepSeek API 生成摘要，返回 {summary, importance, key_points}"""
    api_key = get_config("api_key", "")
    if not api_key:
        return {"summary": "", "importance": 0.5, "key_points": []}

    msgs_text = _format_messages(messages)

    if level == 3 and existing_summaries:
        summaries_text = "\n".join([f"- {s['summary']}" for s in existing_summaries])
        prompt = f"""请基于以下摘要和最新对话，输出一份300字以内的高级摘要。输出 JSON，三个字段都必须有：
{{"summary": "摘要文本", "importance": "低/中/高", "key_points": ["关键信息1", ...]}}
importance 评分：高=涉及个人重要信息/决定/情感，中=日常交流，低=闲聊寒暄

已有摘要：
{summaries_text}

最新对话：
{msgs_text}"""
    else:
        max_len = {1: 50, 2: 150}.get(level, 150)
        prompt = f"""请用{max_len}字以内总结以下对话。输出 JSON，三个字段都必须有：
{{"summary": "摘要文本", "importance": "低/中/高", "key_points": ["关键信息1", ...]}}
importance 评分：高=涉及个人重要信息/决定/情感，中=日常交流，低=闲聊寒暄

对话：
{msgs_text}"""

    base_url = get_config("api_base_url", "https://api.deepseek.com/v1").rstrip("/")
    model = get_config("api_model", "deepseek-chat")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,
        "max_tokens": 500
    }

    try:
        resp = requests.post(f"{base_url}/chat/completions",
                             headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()["choices"][0]["message"]["content"].strip()
        # 剥离 markdown 代码块标记
        for prefix in ['```json', '```']:
            if result.startswith(prefix):
                result = result[len(prefix):].strip()
        for suffix in ['```']:
            if result.endswith(suffix):
                result = result[:-len(suffix)].strip()
        # 如果仍有额外文本包裹，用正则提取 JSON 对象
        if not result.startswith('{'):
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                result = json_match.group(0)
        data = json.loads(result)
        summary = data.get("summary", "")
        importance = IMPORTANCE_MAP.get(str(data.get("importance", "中")).strip(), 0.5)
        key_points = data.get("key_points", [])
        if not isinstance(key_points, list):
            key_points = []
        return {"summary": summary, "importance": importance, "key_points": key_points}
    except (json.JSONDecodeError, KeyError, requests.RequestException) as e:
        print(f"[摘要] Level {level} 生成失败: {e}")
        return {"summary": "", "importance": 0.5, "key_points": []}


# ========== 主流程 ==========
def run_summary_pipeline(msg_count, user_message=""):
    """摘要生成主入口（在后台线程中调用，锁由 run_background_tasks 管理）"""
    tiers = determine_tier(msg_count)
    if not tiers:
        return
    # 先处理高级别，避免低级别插入后影响高级别的消息窗口
    tiers.sort(reverse=True)
    for level in tiers:
        if level == 1:
            msgs = db.get_messages_since_last_tiered_summary(limit=30)
            existing = None
        elif level == 2:
            msgs = db.get_messages_since_last_tiered_summary(limit=50)
            existing = None
        else:  # level 3
            existing = db.get_tiered_summaries_by_level(2)
            if existing:
                msgs = db.get_messages_since_last_tiered_summary(limit=10)
            else:
                msgs = db.get_messages_since_last_tiered_summary(limit=50)
                existing = None
            # 话题关联度检测
            if not check_topic_relevance(user_message):
                print(f"[摘要] Level 3 跳过：话题关联度不足")
                continue

        if not msgs:
            continue

        result = generate_summary_for_tier(level, msgs, existing)
        if not result["summary"]:
            continue

        lifespan = calculate_lifespan(level, result["importance"])

        source_ids = None
        if level == 3 and existing:
            source_ids = [s["id"] for s in existing]

        db.add_tiered_summary(
            level, result["summary"], result["key_points"],
            result["importance"], lifespan,
            msgs[0]["timestamp"], msgs[-1]["timestamp"],
            source_ids
        )
        db.set_last_trigger_at(level, msg_count)
        print(f"[摘要] Level {level} 生成成功，寿命 {lifespan:.1f} 天，重要性 {result['importance']}")


def run_decay_check():
    """每日衰减检查（每天最多执行一次）"""
    last_decay = get_config("_last_decay_date")
    today = datetime.now().strftime("%Y-%m-%d")
    if last_decay == today:
        return 0
    try:
        days = 1 if not last_decay else max(1, (datetime.now() - datetime.fromisoformat(last_decay)).days)
    except (ValueError, TypeError):
        days = 1
    days = min(days, 30)  # 防止长期不用后一次减太多
    db.reset_daily_boost()
    db.decay_summaries(days)
    archived = db.archive_expired_summaries()
    db.set_config("_last_decay_date", today)
    if archived > 0:
        print(f"[衰减] 已归档 {archived} 条过期摘要，减少 {days} 天")
    return days


def run_background_tasks(msg_count, user_message):
    """后台线程入口：衰减 → 提及 → 摘要生成（锁保护全流程）"""
    if not _summary_lock.acquire(blocking=False):
        return
    try:
        run_decay_check()
        process_mentions(user_message)
        run_summary_pipeline(msg_count, user_message)
    except Exception as e:
        print(f"[后台任务] 异常: {e}")
        traceback.print_exc()
    finally:
        _summary_lock.release()
