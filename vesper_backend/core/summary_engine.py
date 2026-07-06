# core/summary_engine.py  |  三级生命周期摘要引擎
"""三级生命周期摘要引擎：基于对话量触发分级摘要，支持衰减、提及续命和反思机制。

摘要级别：
- Level 1：每 10 条消息触发，短期摘要（3-7 天寿命）
- Level 2：每 50 条消息触发，中期摘要（7-30 天寿命）
- Level 3：每 100 条消息触发，长期摘要（30-180 天寿命）
"""
import json
import random
import threading
import logging
from datetime import datetime
from core import db
from core.db import get_config, set_config

logger = logging.getLogger(__name__)

# ========== 常量 ==========
TIER_THRESHOLDS = {1: 10, 2: 50, 3: 100}
TIER_BASE_LIFESPAN = {1: (3, 7), 2: (7, 30), 3: (30, 180)}

# 提及增加档位（占基础寿命中值的比例）
MENTION_BOOST_TIERS = [0.4, 0.6, 0.8, 1.0, 1.2]

# 重要性离散映射
IMPORTANCE_MAP = {"低": 0.2, "中": 0.5, "高": 0.8, "low": 0.2, "medium": 0.5, "high": 0.8}

# 共享 prompt 片段
_SUMMARY_SCHEMA = '{"summary": "摘要文本", "importance": "低/中/高", "key_points": ["关键信息1", ...]}'
_IMPORTANCE_RULES = "importance 评分：高=涉及个人重要信息/决定/情感，中=日常交流，低=闲聊寒暄"
_KEYPOINT_RULES = """key_points 规则（非常重要）：
- 只提取用户的个人信息、偏好、习惯、重要事件、情绪变化、目标计划
- 不要提取：AI的感受/想法、日常问候、天气查询、吃饭建议、闲聊寒暄、AI的回复内容
- 示例正确：["用户叫小明", "用户在上海工作", "用户下周有考试"]
- 示例错误：["助手感到高兴", "用户询问天气", "晚安道别", "助手推荐吃饭"]"""

_summary_lock = threading.Lock()


# ========== 工具函数 ==========
def cosine_sim(a, b):
    """计算两个向量的余弦相似度（纯 Python 实现，不依赖 numpy）。"""
    dot = sum(x * y for x, y in zip(a, b))
    norm = (sum(x * x for x in a) ** 0.5) * (sum(x * x for x in b) ** 0.5)
    return dot / norm if norm else 0.0


def _segment_keywords(text: str) -> set:
    """分词用于关键词匹配（优先 jieba，降级为 2-gram）。"""
    try:
        import jieba
        return {w for w in jieba.cut(text) if len(w.strip()) > 1}
    except ImportError:
        return {text[i:i+2] for i in range(len(text) - 1)}


def calculate_lifespan(level, importance):
    """根据摘要级别和重要性计算随机寿命（天）。"""
    lo, hi = TIER_BASE_LIFESPAN[level]
    base = random.uniform(lo, hi)
    return base * (0.5 + importance) * random.uniform(0.8, 1.2)


def calculate_mention_boost(level, mention_count):
    """根据提及次数计算寿命增量，受每日上限约束。"""
    lo, hi = TIER_BASE_LIFESPAN[level]
    midpoint = (lo + hi) / 2
    base_boost = midpoint * 0.25
    daily_cap = midpoint * 0.4
    tier_index = max(0, min(mention_count, 5) - 1)  # 0-4
    boost = base_boost * MENTION_BOOST_TIERS[tier_index]
    return min(boost, daily_cap)


def calculate_daily_cap(level):
    """计算指定级别摘要的每日寿命增量上限。"""
    lo, hi = TIER_BASE_LIFESPAN[level]
    return ((lo + hi) / 2) * 0.4


def determine_tier(msg_count):
    """根据消息计数返回需要触发的摘要级别列表（差值比较，避免取模漂移）。"""
    tiers = []
    for level, threshold in TIER_THRESHOLDS.items():
        last = db.get_last_trigger_at(level)
        if msg_count - last >= threshold:
            tiers.append(level)
    return tiers


# ========== 话题关联度检测 ==========
def check_topic_relevance(user_message):
    """通过向量相似度检测用户消息与已有摘要的话题关联度。"""
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
    """检测用户消息中是否提及了已有摘要的关键信息，返回被提及的摘要列表。"""
    active = db.get_active_tiered_summaries()
    if not active:
        return []

    mentioned = []
    keyword_hits = []

    # 第一步：key_points 子串匹配（粗筛）
    for s in active:
        kps = s.get("key_points", [])
        if not kps:
            # key_points 为空时回退：用摘要文本前50字匹配（需至少匹配25字）
            prefix = s["summary"][:50]
            if len(prefix) >= 25 and prefix in user_message:
                keyword_hits.append(s)
            continue
        for kp in kps:
            if not isinstance(kp, str):
                continue
            if len(kp) < 2:
                continue
            # 精确子串匹配
            if kp in user_message:
                keyword_hits.append(s)
                break
            # 词语重叠率匹配（向量模型不可用时的降级方案）
            kp_words = _segment_keywords(kp)
            msg_words = _segment_keywords(user_message)
            if kp_words and msg_words:
                overlap = len(kp_words & msg_words)
                union = len(kp_words | msg_words)
                if union > 0 and overlap / union >= 0.4:
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
    """检测用户消息中的摘要提及，并为被提及的摘要增加寿命。"""
    if not user_message or not user_message.strip():
        return
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
    """将消息列表格式化为 role: content 的文本格式。"""
    return "\n".join([f"{m['role']}: {m['content']}" for m in msgs])


def generate_summary_for_tier(level, messages, existing_summaries=None):
    """调用 LLM 为指定级别生成摘要，返回 {summary, importance, key_points}。"""
    api_key = get_config("api_key", "")
    if not api_key:
        return {"summary": "", "importance": 0.5, "key_points": []}

    msgs_text = _format_messages(messages)

    if level == 3 and existing_summaries:
        summaries_text = "\n".join([f"- {s['summary']}" for s in existing_summaries])
        prompt = f"""请基于以下摘要和最新对话，输出一份300字以内的高级摘要。输出 JSON，三个字段都必须有：
{_SUMMARY_SCHEMA}
{_IMPORTANCE_RULES}

{_KEYPOINT_RULES}

已有摘要：
{summaries_text}

最新对话：
{msgs_text}"""
    else:
        max_len = {1: 50, 2: 150}.get(level, 150)
        prompt = f"""请用{max_len}字以内总结以下对话。输出 JSON，三个字段都必须有：
{_SUMMARY_SCHEMA}
{_IMPORTANCE_RULES}

{_KEYPOINT_RULES}

对话：
{msgs_text}"""

    from core.llm_client import call_llm
    data = call_llm(prompt=prompt, temperature=0.5, max_tokens=500, timeout=30, json_mode=True)
    if data:
        summary = data.get("summary", "")
        importance = IMPORTANCE_MAP.get(str(data.get("importance", "中")).strip(), 0.5)
        key_points = data.get("key_points", [])
        if not isinstance(key_points, list):
            key_points = []
        return {"summary": summary, "importance": importance, "key_points": key_points}
    logger.warning(f"[摘要] Level {level} 生成失败")
    return {"summary": "", "importance": 0.5, "key_points": []}


# ========== 主流程 ==========
def run_summary_pipeline(msg_count, user_message="", topic_relevant=True):
    """摘要生成主入口，根据消息计数判断触发级别并生成对应摘要（在后台线程中调用）。"""
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
            if not existing:
                logger.info(f"[摘要] Level 3 跳过：尚无 Level 2 摘要")
                db.set_last_trigger_at(level, msg_count)
                continue
            msgs = db.get_messages_since_last_tiered_summary(limit=10)
            # 话题关联度检测（已在锁外预计算）
            if not topic_relevant:
                logger.info(f"[摘要] Level 3 跳过：话题关联度不足")
                db.set_last_trigger_at(level, msg_count)
                continue

        if not msgs:
            db.set_last_trigger_at(level, msg_count)
            continue

        result = generate_summary_for_tier(level, msgs, existing)
        if not result["summary"]:
            continue

        # 提及权重加成：key_points 命中用户反复提及的短语 → importance +0.2（上限 1.0）
        try:
            from core.mention_tracker import get_top_mentions
            top_mentions = {m["phrase"] for m in get_top_mentions(n=15, min_weight=0.3)}
            if top_mentions and result.get("key_points"):
                import jieba as _jieba
                hit = False
                for kp in result["key_points"]:
                    if not isinstance(kp, str) or len(kp) < 2:
                        continue
                    kp_words = {w for w in _jieba.cut(kp) if len(w) >= 2}
                    if kp_words & top_mentions:
                        hit = True
                        break
                if hit:
                    result["importance"] = min(1.0, result["importance"] + 0.2)
                    logger.debug(f"[摘要] Level {level} 命中高权重 mention，importance 提升至 {result['importance']}")
        except Exception as e:
            logger.debug(f"[摘要] 提及权重查询失败: {e}")

        # 添加时间标记前缀
        time_prefix = ""
        if msgs:
            try:
                first_ts = msgs[0].get("timestamp", "")
                if first_ts:
                    dt = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
                    time_prefix = f"[{dt.strftime('%m-%d')}] "
            except (ValueError, TypeError):
                pass
        result["summary"] = time_prefix + result["summary"]

        lifespan = calculate_lifespan(level, result["importance"])

        # 重要性 >= 0.8 的摘要寿命翻倍
        if result["importance"] >= 0.8:
            lifespan *= 2

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
        logger.info(f"[摘要] Level {level} 生成成功，寿命 {lifespan:.1f} 天，重要性 {result['importance']}")

        # 扫描新 key_points 中的目标/计划
        try:
            from core.goal_tracker import ingest_keypoints
            ingest_keypoints(result.get("key_points", []))
        except Exception as e:
            logger.warning(f"[GoalTracker] 扫描异常: {e}")


def run_decay_check():
    """执行每日衰减检查：重置提及增量、衰减寿命、归档过期摘要（每天最多一次）。"""
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
        logger.info(f"[衰减] 已归档 {archived} 条过期摘要，减少 {days} 天")
    return days


def _generate_rolling_summary():
    """滚动摘要：自动压缩近期对话为摘要，整合已有摘要和新对话（SillyTavern 方案）。"""
    try:
        from core.db import get_recent_chat_messages
        from core.llm_client import call_llm

        # 获取最近 30 条消息
        messages = get_recent_chat_messages(30)
        if not messages or len(messages) < 10:
            return

        # 获取已有滚动摘要
        rolling = db.get_config("_rolling_summary", "")
        new_msgs = messages[-20:]

        conversation = "\n".join([
            f"{'用户' if m['role'] == 'user' else 'AI'}: {m['content'][:300]}"
            for m in new_msgs
        ])

        if rolling:
            # 从结论引擎获取关键实体
            conclusion_hint = ""
            try:
                from core.conclusion_engine import get_active_conclusions
                conclusions = get_active_conclusions(3)
                if conclusions:
                    conclusion_hint = "\n关键实体：" + "、".join([c["text"] for c in conclusions])
            except Exception:
                pass

            prompt = f"""已有摘要：
{rolling}
{conclusion_hint}

新的对话：
{conversation}

请将新对话整合到已有摘要中，生成更新后的摘要。保持简洁（不超过500字），保留关键信息。
只输出摘要文本，不要解释。"""
        else:
            prompt = f"""请将以下对话压缩为一段简洁的摘要（不超过500字），保留关键信息和用户偏好：
{conversation}

只输出摘要文本，不要解释。"""

        result = call_llm(prompt=prompt, temperature=0.3, max_tokens=200, timeout=20)
        if result and len(result) > 20:
            db.set_config("_rolling_summary", result.strip())
            logger.info(f"[滚动摘要] 更新: {result[:60]}...")

    except Exception as e:
        logger.warning(f"[滚动摘要] 生成失败: {e}")


def run_background_tasks(msg_count, user_message):
    """后台线程入口：衰减 → 提及 → 摘要生成 → 滚动摘要 → 反思 → 巩固 → 结论。
    策略：每个大步骤单独加锁释放，避免长时间持锁阻塞下一条消息。"""
    # 话题关联度检查在锁外执行（涉及向量搜索，耗时较长）
    topic_relevant = check_topic_relevance(user_message)

    # Step 1: 衰减 + 提及 + 摘要生成
    if not _summary_lock.acquire(timeout=10):
        logger.warning("[后台任务] 等待超时，本次跳过")
        return
    try:
        run_decay_check()
        process_mentions(user_message)
        run_summary_pipeline(msg_count, user_message, topic_relevant)
    except Exception as e:
        logger.warning(f"[后台任务] 摘要异常: {e}")
    finally:
        _summary_lock.release()

    # Step 2: 滚动摘要（独立加锁）
    if msg_count % 15 == 0 and msg_count > 0:
        if _summary_lock.acquire(timeout=5):
            try:
                _generate_rolling_summary()
            except Exception as e:
                logger.warning(f"[后台任务] 滚动摘要异常: {e}")
            finally:
                _summary_lock.release()

    # Step 3: 关键词 + 反思（独立加锁）
    if _summary_lock.acquire(timeout=5):
        try:
            _update_keyword_strength(_extract_keywords(user_message))
            if msg_count % 30 == 0:
                generate_reflection()
            if msg_count % 50 == 0:
                generate_deep_reflection()
        except Exception as e:
            logger.warning(f"[后台任务] 反思异常: {e}")
        finally:
            _summary_lock.release()

    # Step 4: 记忆巩固（每 100 条消息触发一次）
    if msg_count % 100 == 0 and msg_count > 0:
        try:
            from core.memory_consolidation import consolidate_memories
            result = consolidate_memories()
            if result["consolidated"] > 0:
                logger.info(f"[巩固] {result['report']}")
        except Exception as e:
            logger.warning(f"[后台任务] 记忆巩固异常: {e}")

    # Step 5: 辩证结论分析（每50条）
    if msg_count % 50 == 0 and msg_count >= 50:
        try:
            from core.conclusion_engine import run_conclusion_analysis
            run_conclusion_analysis()
        except Exception as e:
            logger.warning(f"[结论] 分析失败: {e}")


# ========== 反思机制（Stanford Generative Agents）==========
_REFLECTION_PROMPT = """分析以下用户最近的对话，生成一段反思摘要。

要求：
1. 用户最近在关注什么话题？（1-2句）
2. 用户的情绪趋势是什么？（1句）
3. 有什么潜在需求用户没明说？（1句，如果没有写"无"）

对话内容：
{content}

输出格式：
关注：...
情绪：...
潜在需求：..."""


# ─── 分层反思（Generative Agents 方案）───

_KEYWORD_STRENGTH = {}  # {keyword: count}
_KEYWORD_STRENGTH_LOCK = threading.Lock()  # 线程安全锁
_KW_REFLECT_THRESHOLD = 10  # 关键词累积次数达到阈值时触发专题反思


def _load_keyword_strength():
    """从 DB 加载关键词强度（启动时调用）"""
    global _KEYWORD_STRENGTH
    try:
        raw = get_config("_keyword_strength", "")
        if raw:
            _KEYWORD_STRENGTH = json.loads(raw)
    except Exception as e:
        logger.warning(f"[kw] 加载关键词强度失败: {e}")


def _save_keyword_strength():
    """持久化关键词强度到 DB"""
    try:
        with _KEYWORD_STRENGTH_LOCK:
            data = dict(_KEYWORD_STRENGTH)
            set_config("_keyword_strength", json.dumps(data, ensure_ascii=False))
    except Exception as e:
        logger.warning(f"[kw] 保存关键词强度失败: {e}")


# 启动时加载
_load_keyword_strength()


def _extract_keywords(text: str) -> list:
    """提取文本关键词（简易版，使用 jieba 分词并过滤停用词）。"""
    try:
        import jieba
        words = jieba.cut(text)
        return [w for w in words if len(w) > 1 and w not in (
            "用户", "一个", "这个", "那个", "什么", "怎么", "可以", "应该",
            "知道", "觉得", "感觉", "现在", "今天", "昨天", "明天",
        )]
    except ImportError:
        return []


_KW_SAVE_COUNTER = 0


def _update_keyword_strength(keywords: list):
    """更新关键词出现频次（线程安全），定期清理低频词防止内存膨胀。"""
    global _KW_SAVE_COUNTER
    need_save = False
    with _KEYWORD_STRENGTH_LOCK:
        for kw in keywords:
            _KEYWORD_STRENGTH[kw] = _KEYWORD_STRENGTH.get(kw, 0) + 1
        # 定期清理低频关键词，防止内存膨胀
        if len(_KEYWORD_STRENGTH) > 500:
            to_remove = [k for k, v in _KEYWORD_STRENGTH.items() if v < 3]
            for k in to_remove[:len(to_remove)//2]:
                del _KEYWORD_STRENGTH[k]
        _KW_SAVE_COUNTER += 1
        if _KW_SAVE_COUNTER >= 5:
            _KW_SAVE_COUNTER = 0
            need_save = True
    if need_save:
        _save_keyword_strength()


def _check_keyword_reflection_trigger() -> str | None:
    """检查是否有关键词累积次数达到阈值，触发专题反思（线程安全）。"""
    with _KEYWORD_STRENGTH_LOCK:
        for kw, count in list(_KEYWORD_STRENGTH.items()):
            if count >= _KW_REFLECT_THRESHOLD:
                _KEYWORD_STRENGTH[kw] = 0  # 重置
                # 持久化重置，避免重启后重复触发
                try:
                    set_config("_keyword_strength", json.dumps(dict(_KEYWORD_STRENGTH), ensure_ascii=False))
                except Exception:
                    pass
                return kw
    return None


_DEEP_REFLECTION_PROMPT = """基于以下用户信息，生成 3 条高阶洞察。每条洞察必须是关于用户的深层理解。

用户信息：
{content}

要求：
- 每条洞察必须是独立的、有价值的观察
- 不要重复已有信息
- 关注模式、趋势、深层需求
- 用中文输出

输出格式（JSON）：
{{"insights": ["洞察1", "洞察2", "洞察3"]}}"""


def generate_deep_reflection():
    """分层反思：从已有反思和关键词触发中提取更高阶的用户洞察（Generative Agents 方案）。"""
    try:
        from core.db import get_conn, get_recent_chat_messages
        from core.llm_client import call_llm

        # 收集已有反思和近期对话
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT summary, level FROM tiered_summary WHERE remaining_days > 0 ORDER BY level DESC, created_at DESC LIMIT 10"
            )
            existing_reflections = cursor.fetchall()

        if len(existing_reflections) < 2:
            # L2 不足时，尝试从 L1 聚合（防饿死），排除 L3 自身
            with get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT summary, level FROM tiered_summary WHERE remaining_days > 0 AND level < 3 ORDER BY created_at DESC LIMIT 10"
                )
                existing_reflections = cursor.fetchall()
            if len(existing_reflections) < 2:
                return

        # 检查是否有关键词触发
        trigger_kw = _check_keyword_reflection_trigger()
        if not trigger_kw:
            return  # 没有触发

        # 构建输入
        content_parts = []
        for r in existing_reflections:
            content_parts.append(f"[Level {r['level']}] {r['summary']}")

        recent = get_recent_chat_messages(20)
        user_msgs = [m["content"] for m in recent if m.get("role") == "user"]
        if user_msgs:
            content_parts.append("近期用户消息：")
            content_parts.extend(user_msgs[-10:])

        content = "\n".join(content_parts)

        # 调用 LLM 生成深度洞察（用 replace 避免用户消息中的 {} 破坏 format）
        prompt = _DEEP_REFLECTION_PROMPT.replace("{content}", content)
        result = call_llm(prompt=prompt, temperature=0.3, max_tokens=300, timeout=30)
        if not result:
            return

        # 解析结果
        try:
            data = json.loads(result)
            insights = data.get("insights", [])
        except (json.JSONDecodeError, TypeError):
            # 尝试从文本中提取
            insights = [line.strip() for line in result.split("\n") if line.strip() and len(line.strip()) > 10]

        if not insights:
            return

        # 检查与已有反思的重叠（关键词重叠 >= 4 视为重复）
        existing_keywords = set()
        for r in existing_reflections:
            existing_keywords.update(_extract_keywords(r["summary"]))

        new_insights = []
        for insight in insights:
            insight_kws = set(_extract_keywords(insight))
            overlap = len(insight_kws & existing_keywords)
            if overlap < 4:  # 无重叠，是新洞察
                new_insights.append(insight)

        if not new_insights:
            return

        # 存入 level 3 摘要（使用 db 函数确保 consistency）
        now = datetime.now().isoformat()
        lifespan = random.uniform(14, 60) * random.uniform(0.8, 1.2)
        insight_text = "；".join(new_insights[:3])

        db.add_tiered_summary(
            3, insight_text,
            ["深度反思", trigger_kw],
            0.8, lifespan, now, now, None
        )

        logger.info(f"[深度反思] 生成（触发词: {trigger_kw}）: {insight_text[:80]}...")

    except Exception as e:
        logger.warning(f"[深度反思] 生成失败: {e}")


def generate_reflection():
    """从近期对话中生成反思摘要（关注/情绪/潜在需求），存入 Level 2 摘要。"""
    try:
        from core.db import get_recent_chat_messages, get_conn
        from core.llm_client import call_llm

        # 读取最近 50 条用户消息
        messages = get_recent_chat_messages(50)
        user_messages = [m for m in messages if m.get("role") == "user"]

        if len(user_messages) < 10:
            return  # 消息太少，不生成反思

        # 合并消息
        content = "\n".join([f"用户: {m['content']}" for m in user_messages[-30:]])

        # 调用 LLM 生成反思
        prompt = _REFLECTION_PROMPT.replace("{content}", content)
        result = call_llm(prompt=prompt, temperature=0.3, max_tokens=300, timeout=30)

        if not result:
            return

        # 解析反思内容
        lines = result.strip().split("\n")
        reflection_parts = []
        for line in lines:
            line = line.strip()
            if line.startswith("关注：") or line.startswith("关注:"):
                reflection_parts.append(line)
            elif line.startswith("情绪：") or line.startswith("情绪:"):
                reflection_parts.append(line)
            elif line.startswith("潜在需求：") or line.startswith("潜在需求:"):
                reflection_parts.append(line)

        if not reflection_parts:
            return

        reflection_text = "；".join(reflection_parts)

        # 存入 level 2 摘要（使用 db 函数确保 consistency）
        now = datetime.now().isoformat()
        lifespan = random.uniform(7, 30) * random.uniform(0.8, 1.2)

        db.add_tiered_summary(
            2, reflection_text,
            ["反思"],
            0.7, lifespan, now, now, None
        )
        # 更新触发计数器，防止重复生成
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT count FROM summary_msg_counter WHERE id = 1")
            row = cursor.fetchone()
            if row:
                db.set_last_trigger_at(2, row["count"])

        logger.info(f"[反思] 生成: {reflection_text[:80]}...")

    except Exception as e:
        logger.warning(f"[反思] 生成失败: {e}")
