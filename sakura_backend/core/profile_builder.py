"""从对话中提取长期用户画像 + 原子事实（mem0 方案）"""

import json
import hashlib
import threading
from datetime import datetime
from core.db import get_config, get_conn, get_recent_chat_messages
import logging
from core.retry import silent_exc
logger = logging.getLogger(__name__)

_profile_cache = None
_profile_cache_lock = threading.Lock()
_profile_write_lock = threading.Lock()  # 保护 save_profile 的 read-modify-write


def clear_profile_cache():
    """清除画像缓存，删除画像后调用"""
    global _profile_cache
    with _profile_cache_lock:
        _profile_cache = None


def get_profile():
    """获取当前用户画像"""
    global _profile_cache
    with _profile_cache_lock:
        if _profile_cache is not None:
            return dict(_profile_cache)
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value, confidence FROM user_profile WHERE key NOT LIKE '_fact_%'")
        rows = cursor.fetchall()
    cache = {r["key"]: {"value": r["value"], "confidence": r["confidence"]} for r in rows}
    with _profile_cache_lock:
        _profile_cache = cache
    return dict(cache)


def extract_profile_from_messages():
    """从最近对话批量提取用户画像信息"""
    api_key = get_config("api_key", "")
    if not api_key:
        return

    recent = get_recent_chat_messages(100)
    if not recent or len(recent) < 5:
        return
    user_msgs = [m["content"] for m in recent if m.get("role") == "user"]
    if len(user_msgs) < 5:
        return

    existing = get_profile()
    existing_str = "\n".join([f"{k}: {v['value']}" for k, v in existing.items()]) if existing else "无"

    prompt = f"""从以下用户消息中提取用户个人信息。只输出 JSON，不要解释。

已有信息：{existing_str}
用户消息：
{chr(10).join(user_msgs[-30:])}

提取规则（非常重要）：
- 只提取用户自己的信息：昵称、年龄、职业、学校、城市、兴趣爱好、习惯、重要事件
- 不要提取：AI说的话、AI的感受、天气查询、日常问候、吃饭建议、闲聊内容
- 不要提取：用户的临时状态（如"今天好累"），只提取长期特征（如"用户在上海工作"）
- 只输出有把握的，宁缺毋滥
- 置信度规则：明确陈述=0.9，暗示/推断=0.6，猜测=0.3
- 维度分类：bio=基本事实(姓名年龄职业城市)，pref=偏好(喜欢讨厌习惯)，exp=经历，social=社交，work=工作，psy=心理状态
- 初期只提取 bio 和 pref 维度

格式：{{"key": {{"value": "内容", "confidence": 0.0到1.0, "dimension": "bio/pref"}}, ...}}"""

    from core.llm_client import call_llm
    data = call_llm(prompt=prompt, temperature=0.3, max_tokens=400, timeout=20, json_mode=True)
    if data and isinstance(data, dict):
        clean_data = {}
        confidence_map = {}
        for k, v in data.items():
            if isinstance(v, dict) and "value" in v:
                clean_data[k] = str(v["value"])
                try:
                    conf = max(0.0, min(1.0, float(v.get("confidence", 0.7))))
                except (ValueError, TypeError):
                    conf = 0.7
                confidence_map[k] = conf
                dim = v.get("dimension", "")
                if dim:
                    logger.info(f"[画像] 提取: {k}={v['value']} (置信度{conf}, 维度{dim})")
            elif isinstance(v, str):
                clean_data[k] = v
                confidence_map[k] = 0.7
        if clean_data:
            save_profile(clean_data, confidence_map)


def extract_atomic_facts():
    """从对话中提取原子事实（mem0 方案），带哈希去重、时间锚定和生命周期管理"""
    api_key = get_config("api_key", "")
    if not api_key:
        return

    recent = get_recent_chat_messages(30)
    if not recent or len(recent) < 3:
        return

    # 构建对话文本
    conversation = "\n".join([
        f"{'用户' if m['role'] == 'user' else 'AI'}: {m['content']}"
        for m in recent[-20:]
    ])

    # 已有事实（供 LLM 参考去重 + 矛盾检测）
    existing_facts = _get_existing_facts_with_status()
    existing_str = "\n".join(f"- {f['text']} [状态:{f['status']}]" for f in existing_facts[:20]) if existing_facts else "无"

    today = datetime.now().strftime("%Y年%m月%d日")

    prompt = f"""从以下对话中提取用户的原子事实。只输出 JSON，不要解释。

对话日期: {today}
已有事实（不要重复，注意状态）:
{existing_str}

对话:
{conversation}

提取规则:
1. 每条事实必须是独立的、完整的陈述句
2. 只提取用户相关信息，不提取 AI 的信息
3. 跳过寒暄、天气查询、日常问候
4. 包含时间信息时转换为绝对日期（如"昨天"→"{today}"的前一天）
5. 偏好类事实优先提取（喜欢/不喜欢/习惯/偏好）
6. 重要事件优先提取（考试/面试/生日/旅行/工作变动）
7. 不要提取临时状态（"今天好累"），只提取持久事实

**矛盾检测（非常重要）**:
- 如果新事实与已有事实矛盾（如"住在北京"→"搬到了上海"），标记旧事实为 superseded
- 如果新事实表示某个事件已完成（如"快递买的是清理电脑"表示"取快递"已完成），标记旧事实为 completed
- 时效性分类：permanent=永久偏好, event=有始有终的事件, temporary=临时状态

类别:
- preference: 喜好、习惯、偏好
- personal: 姓名、年龄、城市、职业
- event: 重要事件、计划
- social: 人际关系
- work: 工作、学习相关

格式: {{"facts": [{{"text": "事实描述", "category": "类别", "importance": 1-10, "temporality": "permanent/event/temporary"}}], "contradictions": [{{"old_text": "旧事实文本", "action": "completed/superseded"}}]}}"""

    from core.llm_client import call_llm
    data = call_llm(prompt=prompt, temperature=0.2, max_tokens=600, timeout=20, json_mode=True)
    if not data or not isinstance(data, dict):
        return

    # 处理矛盾标记
    contradictions = data.get("contradictions", [])
    if contradictions:
        _handle_contradictions(contradictions)

    facts = data.get("facts", [])
    if not facts:
        return

    # 哈希去重 + 写入
    saved = 0
    with get_conn() as conn:
        cursor = conn.cursor()
        for fact in facts:
            if not isinstance(fact, dict) or "text" not in fact:
                continue
            text = str(fact["text"]).strip()
            if len(text) < 5:
                continue
            fact_hash = hashlib.sha256(text.encode()).hexdigest()
            category = fact.get("category", "general")
            temporality = fact.get("temporality", "permanent")
            try:
                importance = max(1, min(10, int(float(fact.get("importance", 5)))))
            except (ValueError, TypeError):
                importance = 5

            # 检查哈希去重
            cursor.execute("SELECT key FROM user_profile WHERE key = ?", (f"_fact_{fact_hash}",))
            if cursor.fetchone():
                continue

            # 写入（带 status 字段）
            fact_key = f"_fact_{fact_hash}"
            cursor.execute(
                "REPLACE INTO user_profile (key, value, confidence, extracted_at) VALUES (?, ?, ?, ?)",
                (fact_key, json.dumps({
                    "text": text,
                    "category": category,
                    "importance": importance,
                    "temporality": temporality,
                    "status": "active",
                    "created_at": datetime.now().isoformat()
                }, ensure_ascii=False), 0.8, datetime.now().isoformat())
            )
            saved += 1

            # 提取实体并关联（mem0 轻量知识图谱）
            entities = extract_entities_from_text(text)
            for entity_text, entity_type in entities:
                upsert_entity(entity_text, entity_type, fact_key)

    if saved > 0:
        clear_profile_cache()
        logger.info(f"[事实提取] 新增 {saved} 条原子事实")


def _get_existing_facts(limit=50):
    """获取已有原子事实列表"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT value FROM user_profile WHERE key LIKE '_fact_%' ORDER BY extracted_at DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
    facts = []
    for r in rows:
        try:
            d = json.loads(r["value"])
            facts.append(d.get("text", ""))
        except (json.JSONDecodeError, TypeError) as e:
            silent_exc("profile_builder", e)
    return facts


def _get_existing_facts_with_status(limit=50):
    """获取已有原子事实列表（带状态）"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT value FROM user_profile WHERE key LIKE '_fact_%' ORDER BY extracted_at DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
    facts = []
    for r in rows:
        try:
            d = json.loads(r["value"])
            facts.append({
                "text": d.get("text", ""),
                "status": d.get("status", "active"),
                "category": d.get("category", "general"),
            })
        except (json.JSONDecodeError, TypeError) as e:
            silent_exc("profile_builder", e)
    return facts


def _segment_text(text: str) -> list:
    """简易中文分词（优先 jieba，降级为字符）"""
    try:
        import jieba
        return [w for w in jieba.cut(text) if len(w.strip()) > 0]
    except ImportError:
        return list(text)


def _handle_contradictions(contradictions):
    """处理矛盾标记：将旧事实标记为 completed 或 superseded"""
    if not contradictions:
        return
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM user_profile WHERE key LIKE '_fact_%'")
        rows = cursor.fetchall()
        facts_map = {}
        for r in rows:
            try:
                d = json.loads(r["value"])
                facts_map[d.get("text", "")] = (r["key"], d)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"[profile] 事实解析失败: {e}")

        for contra in contradictions:
            old_text = contra.get("old_text", "")
            action = contra.get("action", "superseded")
            if not old_text or action not in ("completed", "superseded"):
                continue
            # 用分词重叠率匹配（比字符集 Jaccard 对短中文更准确）
            old_words = set(_segment_text(old_text))
            for fact_text, (key, data) in facts_map.items():
                if not fact_text:
                    continue
                fact_words = set(_segment_text(fact_text))
                overlap = len(old_words & fact_words)
                union = len(old_words | fact_words)
                if union > 0 and overlap / union >= 0.5:
                    data["status"] = action
                    cursor.execute(
                        "UPDATE user_profile SET value = ? WHERE key = ?",
                        (json.dumps(data, ensure_ascii=False), key)
                    )
                    logger.info(f"[事实生命周期] 标记 {action}: {fact_text[:30]}...")
                    break


def get_facts_context(max_facts=12):
    """获取原子事实上下文，按类型标注注入，带时效性门控。

    时效性规则：
    - temporality=event 超过 30 天 → 不自动注入
    - temporality=temporary 超过 7 天 → 不自动注入
    - 超过时效的仍可通过 vector search 检索到
    """
    from datetime import datetime as _dt
    now = _dt.now()

    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT value FROM user_profile WHERE key LIKE '_fact_%' ORDER BY extracted_at DESC LIMIT ?",
            (max_facts * 3,)
        )
        rows = cursor.fetchall()

    cat_labels = {
        "personal": "基本信息", "preference": "偏好",
        "event": "事件", "work": "工作/学习", "social": "社交",
    }
    by_cat = {}  # category -> [(text_with_time, importance)]
    for r in rows:
        try:
            d = json.loads(r["value"])
            text = d.get("text", "")
            importance = d.get("importance", 5)
            status = d.get("status", "active")
            temporality = d.get("temporality", "permanent")
            created_at = d.get("created_at", "")
            category = d.get("category", "general")
            if not (text and importance >= 4 and status == "active"):
                continue
            # 时效性门控
            if created_at and temporality in ("event", "temporary"):
                try:
                    days = (now - _dt.fromisoformat(created_at)).days
                    if (temporality == "event" and days > 30) or (temporality == "temporary" and days > 7):
                        continue
                    if days > 0:
                        text = f"[{days}天前] {text}"
                    else:
                        text = f"[今天] {text}"
                except Exception:
                    pass
            by_cat.setdefault(category, []).append((text, importance))
        except (json.JSONDecodeError, TypeError):
            pass

    if not by_cat:
        return ""

    lines = []
    # 先输出 personal，再按重要性排序输出其他类型
    for cat in ("personal", "preference", "work", "social", "event", "general"):
        entries = by_cat.get(cat)
        if not entries:
            continue
        label = cat_labels.get(cat, "其他")
        entries.sort(key=lambda x: -x[1])
        cat_lines = []
        for text, _ in entries[:4]:
            cat_lines.append(f"- {text}")
        if cat_lines:
            lines.append(f"【{label}】")
            lines.extend(cat_lines)

    return "\n".join(lines[:max_facts * 2])


# ─── 实体存储（mem0 轻量知识图谱）───

def extract_entities_from_text(text: str) -> list:
    """从文本中提取实体（简易版，用 jieba + 规则）"""
    entities = []
    try:
        import jieba
        import jieba.posseg as pseg
        words = pseg.cut(text)
        for w, flag in words:
            if len(w) < 2:
                continue
            # 人名
            if flag.startswith('nr'):
                entities.append((w, 'PERSON'))
            # 地名
            elif flag.startswith('ns'):
                entities.append((w, 'PLACE'))
            # 机构名
            elif flag.startswith('nt'):
                entities.append((w, 'ORG'))
            # 专有名词
            elif flag.startswith('nz'):
                entities.append((w, 'THING'))
    except ImportError as e:
        silent_exc("profile_builder", e)
    # 引号内文本作为实体
    import re
    for match in re.finditer(r'[「""](.+?)[」""]', text):
        entities.append((match.group(1), 'THING'))
    return entities


def upsert_entity(entity_text: str, entity_type: str, memory_key: str):
    """插入或更新实体，关联到记忆"""
    import hashlib
    entity_hash = hashlib.sha256(entity_text.lower().encode()).hexdigest()
    with get_conn() as conn:
        cursor = conn.cursor()
        # 检查是否已存在
        cursor.execute("SELECT id, linked_memories FROM entities WHERE entity_hash = ?", (entity_hash,))
        row = cursor.fetchone()
        if row:
            # 更新：追加关联记忆
            try:
                existing = set(json.loads(row["linked_memories"]) if row["linked_memories"] else [])
            except (json.JSONDecodeError, TypeError):
                existing = set()
            existing.add(memory_key)
            cursor.execute("UPDATE entities SET linked_memories = ?, entity_type = ? WHERE id = ?",
                          (json.dumps(list(existing)), entity_type, row["id"]))
        else:
            # 新建
            cursor.execute(
                "INSERT INTO entities (entity_text, entity_type, entity_hash, linked_memories, created_at) VALUES (?, ?, ?, ?, ?)",
                (entity_text, entity_type, entity_hash, json.dumps([memory_key]), datetime.now().isoformat())
            )


def get_entity_context(query: str, max_entities: int = 5) -> str:
    """从查询中提取实体，返回关联的上下文"""
    entities = extract_entities_from_text(query)
    if not entities:
        return ""
    contexts = []
    with get_conn() as conn:
        cursor = conn.cursor()
        for entity_text, entity_type in entities[:3]:  # 最多查 3 个实体
            entity_hash = hashlib.sha256(entity_text.lower().encode()).hexdigest()
            cursor.execute("SELECT linked_memories FROM entities WHERE entity_hash = ?", (entity_hash,))
            row = cursor.fetchone()
            if row and row["linked_memories"]:
                try:
                    memory_keys = json.loads(row["linked_memories"])
                except (json.JSONDecodeError, TypeError):
                    continue
                # 获取关联记忆的内容
                for mk in memory_keys[:2]:  # 每个实体最多取 2 条关联记忆
                    cursor.execute("SELECT value FROM user_profile WHERE key = ?", (mk,))
                    mem = cursor.fetchone()
                    if mem:
                        try:
                            d = json.loads(mem["value"])
                            contexts.append(f"{entity_text}: {d.get('text', '')}")
                        except Exception:
                            contexts.append(f"{entity_text}: {mem['value']}")
    if not contexts:
        return ""
    return "【实体关联】\n" + "\n".join(contexts[:max_entities])


def save_profile(data: dict, confidence_map: dict = None):
    """保存画像条目（带置信度合并逻辑）"""
    global _profile_cache
    from datetime import datetime
    with _profile_write_lock:  # 防并发写入
        if confidence_map is None:
            confidence_map = {k: 0.7 for k in data}
        existing = get_profile()
        now = datetime.now().isoformat()
        with get_conn() as conn:
            cursor = conn.cursor()
            for key, value in data.items():
                new_conf = confidence_map.get(key, 0.7)
                old = existing.get(key)
                if old:
                    old_conf = old.get("confidence", 0.5)
                    old_val = old.get("value", "")
                    if old_val == str(value):
                        final_conf = max(old_conf, new_conf)
                        cursor.execute("REPLACE INTO user_profile (key, value, confidence, extracted_at) VALUES (?, ?, ?, ?)", (str(key), str(value), final_conf, now))
                    elif new_conf > old_conf:
                        cursor.execute("REPLACE INTO user_profile (key, value, confidence, extracted_at) VALUES (?, ?, ?, ?)", (str(key), str(value), new_conf, now))
                else:
                    cursor.execute("REPLACE INTO user_profile (key, value, confidence, extracted_at) VALUES (?, ?, ?, ?)", (str(key), str(value), new_conf, now))
        # 缓存失效移入锁内部，避免窗口期内读到旧缓存
        with _profile_cache_lock:
            _profile_cache = None


_CORE_PROFILE_KEYS = {
    "name", "gender", "age", "city", "birthday", "occupation",
    "personality", "hobby", "zodiac", "mbti",
}


def cleanup_expired_profile(days: int = 90):
    global _profile_cache
    from datetime import datetime, timedelta
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    with get_conn() as conn:
        cursor = conn.cursor()
        # 保护核心身份字段、原子事实、高置信度条目
        cursor.execute(
            "DELETE FROM user_profile WHERE extracted_at < ? "
            "AND key NOT IN ({}) AND key NOT LIKE '_fact_%'".format(",".join("?" * len(_CORE_PROFILE_KEYS))),
            [cutoff, *_CORE_PROFILE_KEYS],
        )
        deleted = cursor.rowcount
    with _profile_cache_lock:
        _profile_cache = None
    if deleted > 0:
        logger.info(f"[画像] 清理 {deleted} 条过期条目（>{days}天）")
    return deleted


def get_profile_context():
    """生成画像上下文文本，用于注入 system prompt"""
    profile = get_profile()
    if not profile:
        return ""

    sections = {"_plan_": "【待办计划】", "_progress_": "【进行中】", "_event_": "【已完成】"}
    category_items = {key: [] for key in sections}
    other_items = []

    for k, v in profile.items():
        conf = v.get("confidence", 0)
        if conf < 0.55:
            continue
        val = v["value"]
        if 0.55 <= conf < 0.7:
            val = f"{val}（仅供参考）"

        matched = False
        for prefix in sections:
            if k.startswith(prefix):
                category_items[prefix].append(f"{k[len(prefix):]}: {val}")
                matched = True
                break
        if not matched and not k.startswith("_"):
            other_items.append(f"{k}: {val}")

    parts = []
    for prefix, label in sections.items():
        if category_items[prefix]:
            parts.append(label)
            parts.extend(category_items[prefix])
    if other_items:
        parts.append("【用户画像】")
        parts.extend(other_items)

    if not parts:
        return ""
    return "\n".join(parts)


def clear_completed_plans():
    """已完成的事件清除对应的计划和进行中状态"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key FROM user_profile WHERE key LIKE '_event_%'")
        done_events = [r["key"].replace("_event_", "") for r in cursor.fetchall()]
        for cat in done_events:
            cursor.execute("DELETE FROM user_profile WHERE key IN (?, ?)",
                          (f"_plan_{cat}", f"_progress_{cat}"))
        conn.commit()
    clear_profile_cache()


# ─── 事件完成追踪 ───

# 事件完成检测正则（按优先级排列，匹配即返回）
_COMPLETION_REGEX = [
    # 1. 特定结构：去了XXX、去了趟XXX
    r"(?:去了|去了趟|去.*?了)\S{0,8}?(?:店|院|馆|局|厅|理发|剪发|取|寄|买|吃|看|办|拿)",

    # 2. 回来了/到家了/搞定了（短匹配优先）
    r"\S{0,6}(?:回来|过来了|到家|搞定|弄好)(?:了|的)",

    # 3. XX完了/好了/到了/过了
    r"\S{1,6}(?:完了|好了|到了|过了|掉了|妥了)",

    # 4. 才/刚 XXX（刚剪完/才回来/刚考完试）
    r"(?:才|刚)\S{1,12}",

    # 5. 我去/我刚刚/我刚 XX了
    r"(?:我去|我刚刚|我刚)\S{1,15}了",

    # 6. 单字动+了+结束/标点/名词（吃了烧烤/剪了头发）排除疑问/否定
    r"(?:买|吃|喝|剪|理|洗|修|做|写|看|读|发|寄|送|取|拿|弄|办|考)了(?!(?:吗|么|没|什么|啥|就|不))\S{0,4}(?:$|[。！？]|\s|的|个|一|点|碗|顿|次|下|趟)",
]

# 事件类型关键词映射（用于生成可读的 key）
_EVENT_TYPES = {
    "头发": "理发",
    "饭|吃|喝|烧烤|麻辣烫|火锅": "吃饭",
    "快递|取": "快递",
    "考": "考试",
    "买|购物": "购物",
    "修|搞|弄|办": "办理",
    "写|做|看|读": "作业",
    "洗|打扫|整理": "家务",
    "发|寄|送": "寄送",
}


def _categorize_event(user_message: str) -> str:
    """对事件分类"""
    for pattern, category in _EVENT_TYPES.items():
        import re
        if re.search(pattern, user_message):
            return category
    return "事项"


# ─── 计划检测正则 ───
_PLAN_REGEX = [
    # 我要/想去/打算/准备 去做某事（排除疑问句）
    r"(?:(?:我|我们))?(?:要|想去|打算|准备|计划|得去|该去|该)\S{0,3}(?:去|来|把|给)\S{3,15}(?![吗么？？])",
    # 还没做某事
    r"还没(?!(?:确定|知道|说完|说完|说完|完事|结束))\S{2,12}",
]

_IN_PROGRESS_REGEX = [
    r"(?:正在|正)\S{3,12}(?:。|！|$|\.)",
    r"在\S{2,8}(?:中|着|呢)(?:。|！|$|\.)",
]


def _save_profile_event(key: str, value: str, confidence: float = 0.9):
    """写入 user_profile"""
    with _profile_write_lock:
        with get_conn() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                "INSERT OR REPLACE INTO user_profile (key, value, confidence, extracted_at) VALUES (?, ?, ?, ?)",
                (key, value, confidence, now)
            )
            conn.commit()
        clear_profile_cache()


def track_event_completion(user_message: str):
    """检测用户是否完成某事件，写入 user_profile"""
    import re
    for pattern in _COMPLETION_REGEX:
        if re.search(pattern, user_message):
            category = _categorize_event(user_message)
            key = f"_event_{category}"

            with _profile_write_lock:
                with get_conn() as conn:
                    cursor = conn.cursor()
                    now = datetime.now().isoformat()
                    cursor.execute(
                        "INSERT OR REPLACE INTO user_profile (key, value, confidence, extracted_at) VALUES (?, ?, ?, ?)",
                        (key, f"已完成（{datetime.now().strftime('%m-%d')}）", 0.9, now)
                    )
                    conn.commit()
                clear_profile_cache()
            return True
    return False


def track_plan_intent(user_message: str):
    """检测用户是否表达计划/意图，写入 user_profile"""
    import re
    for pattern in _PLAN_REGEX:
        if re.search(pattern, user_message):
            category = _categorize_event(user_message)
            _save_profile_event(f"_plan_{category}", f"计划中（{datetime.now().strftime('%m-%d')}）", 0.85)
            return True
    return False


def track_in_progress(user_message: str):
    """检测用户是否正在做某事"""
    import re
    for pattern in _IN_PROGRESS_REGEX:
        if re.search(pattern, user_message):
            category = _categorize_event(user_message)
            _save_profile_event(f"_progress_{category}", f"进行中（{datetime.now().strftime('%m-%d')}）", 0.85)
            return True
    return False
