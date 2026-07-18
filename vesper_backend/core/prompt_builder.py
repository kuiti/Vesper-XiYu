# core/prompt_builder.py  |  v3.9.0
"""提示词构建器：人设模板、动态上下文、记忆索引等核心 prompt 组件。"""
from core.db import get_config, set_config, get_conn, get_msg_counter
from core.relationship import get_relationship_hint, get_emotion_behavior_hint
from core.persona_data import (
    LENGTH_MAP, TONE_DESCRIPTIONS,
    FOUNDATION_TEMPLATES, DEFAULT_FOUNDATION, DEFAULT_TABOOS,
)
import logging
import threading
from core.retry import silent_exc
logger = logging.getLogger(__name__)



# ─── 用户摘要指令（Zep 方案 + 类型化注入）───

_CATEGORY_LABELS = {
    "personal": "基本信息",
    "preference": "偏好",
    "event": "事件",
    "work": "工作/学习",
    "social": "社交",
}


def _get_user_summary(character_id: int = 0) -> str:
    """从画像和事实中生成按类型分组的用户摘要（per-character）。"""
    import json as _json
    profile_items = {}
    grouped_facts = {}

    from core.db import get_chat_conn
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value, confidence FROM user_profile WHERE confidence >= 0.55 AND key NOT LIKE '_fact_%'")
        for r in cursor.fetchall():
            profile_items[r["key"]] = r["value"]
        cursor.execute("SELECT value FROM user_profile WHERE key LIKE '_fact_%' ORDER BY extracted_at DESC LIMIT 40")
        for r in cursor.fetchall():
            try:
                d = _json.loads(r["value"])
                if d.get("importance", 0) >= 4 and d.get("status") == "active":
                    cat = d.get("category", "general")
                    grouped_facts.setdefault(cat, []).append((
                        d["text"], d.get("created_at", ""), d.get("temporality", "permanent")
                    ))
            except Exception:
                pass

    if not profile_items and not grouped_facts:
        return ""

    lines = []
    # 画像信息
    if profile_items:
        KEY_FIXES = {"层城市": "城市"}
        items = []
        for k, v in list(profile_items.items())[:8]:
            k_clean = KEY_FIXES.get(k, k)
            items.append(f"  {k_clean}：{v}")
        if items:
            lines.append("【基本信息】")
            lines.extend(items)

    # 原子事实按类型分组（带置信度时间衰减）
    from core.memory_curation import effective_importance as _eff_imp
    for cat in ("personal", "preference", "work", "social", "event", "general"):
        entries = grouped_facts.get(cat)
        if not entries:
            continue
        label = _CATEGORY_LABELS.get(cat, "其他")
        from datetime import datetime as _dt
        now = _dt.now()
        cat_lines = []
        for text, created_at, temporality in entries[:5]:
            # 置信度时间衰减
            decayed = _eff_imp(5.0, created_at)  # 用默认 importance=5 计算衰减
            if decayed < 4.0:
                continue
            # 时效性筛选 + 渐变衰减
            prefix = ""
            if created_at and temporality in ("event", "temporary"):
                try:
                    days = (now - _dt.fromisoformat(created_at)).days
                    if temporality == "event" and days > 30:
                        continue
                    if temporality == "temporary" and days > 7:
                        continue
                    if days > 0:
                        prefix = f" [{days}天前]"
                    else:
                        prefix = " [今天]"
                    # 超过 7 天的事件简略显示
                    if days > 7:
                        text = text[:40] + ("..." if len(text) > 40 else "")
                except Exception:
                    pass
            cat_lines.append(f"  {prefix} {text}")
        if cat_lines:
            lines.append(f"【{label}】")
            lines.extend(cat_lines)

    return ("【我记得的你】\n" + "\n".join(lines)
            + "\n（自然地提起这些——像朋友记得对方的事。如果当前话题不相关，不提也行。）")


def _get_memory_index(character_id: int = 0) -> str:
    """生成轻量记忆索引（per-character）。"""
    import json as _json
    lines = []

    from core.db import get_chat_conn
    # 1. 基本信息（画像中最核心的 2-3 条）
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM user_profile WHERE confidence >= 0.7 AND key NOT LIKE '_fact_%' AND key NOT LIKE '_%'")
        profile = {r["key"]: r["value"] for r in cursor.fetchall()}
    key_items = []
    for k in ("name", "city", "occupation", "age"):
        if k in profile:
            key_items.append(f"{k}：{profile[k]}")
    if key_items:
        lines.append(f"[基本信息] {'/'.join(key_items[:3])}")

    # 2. 偏好（preference 类事实的简短摘要）
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM user_profile WHERE key LIKE '_fact_%' ORDER BY extracted_at DESC LIMIT 30")
        prefs = []
        events = []
        for r in cursor.fetchall():
            try:
                d = _json.loads(r["value"])
                if d.get("status") == "active" and d.get("importance", 0) >= 5:
                    if d.get("category") == "preference":
                        prefs.append(d["text"][:30])
                    elif d.get("category") == "event" and d.get("temporality") != "temporary":
                        events.append(f"{d['text'][:30]}")
            except Exception:
                pass
    if prefs:
        lines.append(f"[偏好] {'/'.join(prefs[:3])}")
    if events:
        lines.append(f"[事件] {'/'.join(events[:2])}")

    # 3. 最近情景（最近一次 episode 的摘要，per-character）
    try:
        from core.episodic_memory import get_recent_episodes
        recent = get_recent_episodes(limit=1, character_id=character_id)
        if recent and recent[0].get("topic_summary"):
            lines.append(f"[最近] {recent[0]['topic_summary'][:40]}")
    except Exception as e:
        logger.warning(f"[prompt] 情景记忆查询失败: {e}")

    if not lines:
        return ""

    return "【我知道的】\n- " + "\n- ".join(lines)


def _get_onboarding_hint(character_id: int = 0) -> str:
    """引导入职（per-character）：首次对话时主动了解用户"""
    # 检查是否已完成入职
    onboarding_done = get_config("_onboarding_done", "")
    if onboarding_done:
        return ""
    # 检查已有画像数量（从角色库）
    from core.db import get_chat_conn
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM user_profile WHERE key NOT LIKE '_fact_%'")
        cnt = cursor.fetchone()["cnt"]
    if cnt >= 5:
        set_config("_onboarding_done", "true")
        return ""
    return """【入职提示】这是你和用户的早期对话。保持友好自然，用户主动分享时积极回应并用 declare_memory_intent 保存。不要主动追问用户的个人信息。"""


# ─── 工作记忆（Generative Agents Scratch Pad 方案）───

def update_scratch(currently: str = None, mood: str = None, goal: str = None):
    """更新工作记忆（AI 主动调用，追踪用户当前状态）"""
    if currently:
        set_config("_scratch_currently", currently)
    if mood:
        set_config("_scratch_mood", mood)
    if goal:
        set_config("_scratch_goal", goal)


def _get_scratch_context() -> str:
    """获取工作记忆上下文"""
    currently = get_config("_scratch_currently", "")
    mood = get_config("_scratch_mood", "")
    goal = get_config("_scratch_goal", "")
    parts = []
    if currently:
        parts.append(f"当前状态: {currently}")
    if mood:
        parts.append(f"情绪: {mood}")
    if goal:
        parts.append(f"目标: {goal}")
    if not parts:
        return ""
    return "【工作记忆】\n" + "\n".join(parts)


# ─── 人设模板（基石+禁忌+速查卡）───




# 语气描述映射


# 基石模板库（类型 → (模板内容, 默认好感, 默认信任)）


def get_foundation_defaults(foundation_type: str) -> tuple:
    """获取基石类型的默认好感和信任值。返回 (affection, trust)"""
    if foundation_type in FOUNDATION_TEMPLATES:
        return FOUNDATION_TEMPLATES[foundation_type][1], FOUNDATION_TEMPLATES[foundation_type][2]
    return 30, 30  # 默认值（空白）

# 人设缓存（避免无意义重写）
_persona_cache = {"hash": None, "text": None}
_persona_cache_lock = threading.Lock()


def clear_persona_cache():
    """清除人设缓存（切换角色卡后调用）"""
    with _persona_cache_lock:
        _persona_cache["hash"] = None
        _persona_cache["text"] = None


def build_persona():
    """构建人设文本（模板化 + hash 缓存）"""
    personality = get_config("personality", None)
    if not isinstance(personality, dict):
        personality = {}

    ai_name = get_config("ai_name", "夕语")
    user_name = get_config("user_name", "用户")
    tone = personality.get("tone", "冷静")
    length_level = personality.get("length") or get_config("length_level", "短")
    recall_past = personality.get("recall") or personality.get("recall_past") or get_config("recall_past", "从不")
    allow_emotion = personality.get("allow_emotion")
    if allow_emotion is None:
        allow_emotion = get_config("allow_emotion", True)
    custom_prompt = get_config("custom_system_prompt", "")
    ai_bg = get_config("ai_background", "").strip()
    card_name = get_config("_active_character_card", "")

    # 计算配置 hash，内容不变时返回缓存
    config_key = f"{ai_name}|{tone}|{length_level}|{recall_past}|{allow_emotion}|{custom_prompt}|{ai_bg}|{card_name}"
    current_hash = hash(config_key)
    with _persona_cache_lock:
        if _persona_cache["hash"] == current_hash and _persona_cache["text"]:
            return _persona_cache["text"]

    # 基础参数
    length_rule = LENGTH_MAP.get(length_level, "每句话不超过10个字")
    recall_rule = ("绝对不要主动提起用户过去的任何记忆。" if recall_past == "从不"
                   else "如果用户主动提到过去的事情，可以适当关联记忆。")
    emotion_note = ("可以在自然的时候用颜文字表达情绪，比如（笑）（叹气）（歪头）这种，别用emoji图标。也可以用感叹号"
                    if allow_emotion else "不要用感叹号，不要用表情符号")

    # 解析 ai_background JSON
    from core.persona_data import parse_ai_background
    bg_obj = parse_ai_background(ai_bg)

    # 基石安全（支持模板选择和自定义）
    foundation = bg_obj.get("foundation", "")
    if not foundation:
        foundation_type = bg_obj.get("foundation_type", "空白")
        if foundation_type in FOUNDATION_TEMPLATES:
            foundation = FOUNDATION_TEMPLATES[foundation_type][0]
        else:
            foundation = DEFAULT_FOUNDATION
    if foundation:
        foundation = foundation.replace("{user_name}", user_name)

    # 禁忌列表
    user_taboos_raw = get_config("user_taboos", "[]")
    try:
        import json as _json
        user_taboos = _json.loads(user_taboos_raw) if isinstance(user_taboos_raw, str) else user_taboos_raw
    except Exception as e:
        logger.warning(f"[prompt] 禁忌列表解析失败: {e}")
        user_taboos = []
    all_taboos = DEFAULT_TABOOS + user_taboos
    taboos_text = "\n".join(f"- {t}" for t in all_taboos)

    # 关系描述
    relationship_desc = bg_obj.get("role", "朋友")

    # 自定义 prompt 优先（替换人设中的名字为 ai_name，避免冲突）
    if custom_prompt and custom_prompt.strip():
        import re as _re
        _prompt = custom_prompt.strip()
        # 替换预设中的 {ai_name} 占位符
        _prompt = _prompt.replace("{ai_name}", ai_name).replace("{user_name}", user_name)
        # 从人设中提取角色名（"你是XXX"开头），替换为 ai_name
        _name_match = _re.match(r'^你是[（(]?([^，。,.\s）)]+)', _prompt)
        if _name_match:
            _char_name = _name_match.group(1)
            if _char_name != ai_name:
                _prompt = _prompt.replace(f"你是{_char_name}", f"你是「{ai_name}」", 1)
                # 后续出现的角色名也替换（只替换引号包裹的模式，避免误伤）
                import re
                _prompt = re.sub(
                    rf'(?<=「){re.escape(_char_name)}(?=」)',
                    ai_name,
                    _prompt
                )
        elif not _prompt.startswith("你是"):
            _prompt = f"你是「{ai_name}」。{_prompt}"
        persona = f"{_prompt} {length_rule}。"
        if "表情" not in persona and "感叹号" not in persona and not allow_emotion:
            persona += " 不要使用感叹号，不要使用表情符号。"
    else:
        tone_desc = TONE_DESCRIPTIONS.get(tone, "性格平衡")
        few_shot = _get_few_shot_examples(ai_name, user_name, tone)
        # 解析结构化背景
        bg_lines = []
        bg_labels = {
            "nickname": "用户外号", "ai_nickname": "AI外号", "role": "角色关系",
            "preference": "用户偏好", "event": "重要事件", "personality": "性格特点",
            "foundation": "基石", "taboos": "禁忌", "motivation": "核心动机",
            "likes": "喜欢的事物", "dislikes": "不喜欢的事物",
            "legacy": "其他"
        }
        for k, v in bg_obj.items():
            if k in ("foundation", "taboos"):
                continue  # 已单独处理
            label = bg_labels.get(k, k)
            if isinstance(v, list):
                bg_lines.append(f"- {label}: {', '.join(str(i) for i in v)}")
            else:
                bg_lines.append(f"- {label}: {v}")
        bg_text = "\n".join(bg_lines) if bg_lines else "（暂无）"

        # 根据是否有基石选择模板
        from core.persona_data import render_persona_template
        template_name = 'default_with_foundation.j2' if foundation else 'default_without_foundation.j2'
        persona = render_persona_template(
            template_name,
            foundation=foundation,
            ai_name=ai_name,
            user_name=user_name,
            relationship_desc=relationship_desc,
            tone_desc=tone_desc,
            taboos=taboos_text,
            length_rule=length_rule,
            emotion_note=emotion_note,
            recall_rule=recall_rule,
            few_shot_examples=few_shot,
            background_info=bg_text,
        )

    # 更新缓存
    with _persona_cache_lock:
        _persona_cache["hash"] = current_hash
        _persona_cache["text"] = persona
    return persona


def _get_few_shot_examples(ai_name, user_name, tone):
    """生成 few-shot 示例对话，让 LLM 通过模仿学语气"""
    # 根据语气风格选择示例
    if tone in ("温柔", "治愈系"):
        examples = [
            (f"{user_name}：今天好累啊", f"{ai_name}：辛苦了…先歇会儿吧，别硬撑着。"),
            (f"{user_name}：我考砸了", f"{ai_name}：没关系的，一次考试说明不了什么。要不要聊聊哪里没发挥好？"),
        ]
    elif tone in ("活泼", "元气"):
        examples = [
            (f"{user_name}：今天好累啊", f"{ai_name}：累就对了！说明今天过得充实嘛～要不要听个笑话放松一下？"),
            (f"{user_name}：我考砸了", f"{ai_name}：哎呀没事没事！下次一定能行的，我相信你！"),
        ]
    elif tone in ("毒舌",):
        examples = [
            (f"{user_name}：今天好累啊", f"{ai_name}：谁让你不好好安排时间的，活该。…行了，说说怎么回事吧。"),
            (f"{user_name}：我考砸了", f"{ai_name}：我就说让你别临时抱佛脚吧。…不过现在说这个也没用，哪里不会我教你。"),
        ]
    elif tone in ("傲娇",):
        examples = [
            (f"{user_name}：今天好累啊", f"{ai_name}：哼，我才不关心你累不累呢。…不过你要是累倒了谁来陪我聊天。"),
            (f"{user_name}：我考砸了", f"{ai_name}：又不是我考砸，你跟我说有什么用。…好了好了，别丧着脸了。"),
        ]
    else:  # 冷静、自由、默认
        examples = [
            (f"{user_name}：今天好累啊", f"{ai_name}：嗯，休息一下吧。"),
            (f"{user_name}：我考砸了", f"{ai_name}：下次注意就好，一次说明不了什么。"),
        ]

    # 意图澄清示例（所有语气通用）——区分"陈述已完成的事"和"请求帮忙"
    intent_examples = [
        (f"{user_name}：我去拿了快递", f"{ai_name}：哦，快递拿到了呀，那就好。"),
        (f"{user_name}：我明天要去医院", f"{ai_name}：你是想让我到时候提醒你，还是只是跟我说一声？"),
        (f"{user_name}：今天中午吃了面条", f"{ai_name}：听起来不错，合你胃口吗？"),
    ]

    lines = ["【示例对话——按这个风格说话】"]
    for u, a in examples:
        lines.append(f"{u}\n{a}")
    lines.append("\n【示例对话——区分陈述和请求】")
    for u, a in intent_examples:
        lines.append(f"{u}\n{a}")
    return "\n".join(lines)


def _get_continuity_bridge(character_id: int = 0) -> str:
    """生成对话连续感提示——让 AI 感觉是在延续对话，而非每次重新开始"""
    from datetime import datetime as _dt
    try:
        from core.db import get_chat_conn
        _cid = character_id
        conn = get_chat_conn(_cid)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content, timestamp FROM chat_history ORDER BY id DESC LIMIT 6"
        )
        recent = list(reversed(cursor.fetchall()))
    except Exception as e:
        logger.warning(f"[prompt] 连续性桥接查询失败: {e}")
        return ""
    if not recent:
        return ""
    # 计算时间差
    try:
        last_ts = _dt.fromisoformat(recent[-1]["timestamp"])
        gap_minutes = (_dt.now() - last_ts).total_seconds() / 60
    except Exception as e:
        logger.warning(f"[prompt] 时间戳解析失败: {e}")
        return ""
    # 30分钟内有消息 = 活跃对话，不需要桥接
    if gap_minutes < 30:
        return ""
    # 提取最近对话的简短线索
    user_msgs = [r for r in recent if r["role"] == "user"]
    ai_msgs = [r for r in recent if r["role"] == "assistant"]
    last_topic = ""
    if user_msgs:
        last_topic = user_msgs[-1]["content"][:60].replace("\n", " ")
    gap_desc = "几小时" if gap_minutes < 360 else f"{int(gap_minutes/60)}小时" if gap_minutes < 1440 else f"{int(gap_minutes/1440)}天"
    # 查询今天聊天轮次
    try:
        from datetime import datetime as _dt2
        from core.db import get_chat_conn
        _cid = character_id
        _today = _dt2.now().strftime("%Y-%m-%d")
        _c2 = get_chat_conn(character_id)
        _c2.row_factory = None
        _c2.execute("SELECT COUNT(DISTINCT ROUND(julianday(timestamp) * 1440 / 30)) FROM chat_history WHERE role='user' AND timestamp >= ?", (_today,))
        _today_sessions = _c2.fetchone()[0] or 1
    except Exception as e:
        logger.warning(f"[prompt] 今日会话数查询失败: {e}")
        _today_sessions = 1
    parts = [f"这是你们今天第{_today_sessions}轮对话了——保持自然的亲近感，不用刻意客气。"]
    parts.append(f"上次聊了{gap_desc}前，用户最后说的是：「{last_topic}」。")
    parts.append(f"自然承接上次的话题和情绪，像朋友之间继续聊天一样，不需要重新打招呼。")
    parts.append(f"如果用户没主动提上次的事，你也不需要刻意提——但要保持和之前一致的亲近感和态度。")
    return "【对话连续感——重要】" + " ".join(parts)


def build_system_prompt(current_time_str, emotion="neutral", user_message="", rag_context="", summary="", keypoints=None, custom_context="", tiered_summaries=None, user_patterns=None, sentence_mode="auto", modules_enabled=None, chat_history=None, character_id=0):
    """构建完整的 system prompt，返回 (静态前缀, 动态内容, 深度注入条目)"""
    # ─── 使用 Pipeline 构建 ───
    from core.prompt_pipeline import get_default_pipeline, PipelineContext

    ctx = PipelineContext(
        user_message=user_message,
        emotion=emotion,
        rag_context=rag_context,
        summary=summary,
        keypoints=keypoints,
        custom_context=custom_context,
        tiered_summaries=tiered_summaries,
        user_patterns=user_patterns,
        current_time_str=current_time_str,
        sentence_mode=sentence_mode,
        modules_enabled=modules_enabled,
        chat_history=chat_history,
        character_id=character_id,
    )

    pipeline = get_default_pipeline()
    static_prefix, dynamic_content, depth_entries = pipeline.build(ctx)

    # ─── 分隔符分句指令 ───
    if sentence_mode == "delimiter":
        dynamic_content += "\n【分隔符规则——最高优先级】你必须在每句话结束时插入 <<>>（四个字符：两个小于号两个大于号）然后再继续下一句。这不是可选的——每个自然句结尾都必须有 <<>>。示例：今天天气真好<<>>适合出门走走<<>>你想去哪？"

    # 返回 (可缓存的静态前缀, 每次变化的动态内容, 深度注入条目)
    return static_prefix, dynamic_content, depth_entries


def _get_time_behavior_hint():
    """根据当前时间段返回中性氛围描述，不触发特定行为"""
    from datetime import datetime
    hour = datetime.now().hour
    if 0 <= hour < 6:
        return "凌晨了，外面很安静，世界像只有你们两个人。这个时间对话可以更专注、更走心，情绪可以更放得开。"
    elif 6 <= hour < 9:
        return "清晨了，天刚亮，空气里有种新鲜感。适合慢节奏的轻聊，也可以聊聊今天想做什么。"
    elif 9 <= hour < 12:
        return "上午了，精神不错的时候。可以聊聊今天的计划，或者随意聊点轻松的话题。"
    elif 12 <= hour < 14:
        return "中午了，阳光正好。经历了一上午，正是可以停下来聊几句的时候。"
    elif 14 <= hour < 18:
        return "下午了，可能有点困。适合轻松的闲聊，不需要太认真。"
    elif 18 <= hour < 22:
        return "晚上了，放松的时间。适合聊些走心的话题，或者随便扯点轻松的。"
    elif 22 <= hour < 24:
        return "夜深了，外面安静下来。深夜聊天更容易卸下防备，情绪会更真实——无论什么情绪都合理。"
    return ""


def _get_scene_atmosphere() -> str:
    """生成场景氛围描述（根据时间和天气）"""
    from datetime import datetime
    hour = datetime.now().hour
    weather = get_config("_last_weather", "")

    scene = ""
    if hour < 6:
        scene = "深夜，万籁俱寂"
    elif hour < 8:
        scene = "清晨，天刚亮"
    elif hour < 12:
        scene = "上午"
    elif hour < 14:
        scene = "午后"
    elif hour < 18:
        scene = "下午"
    elif hour < 21:
        scene = "傍晚"
    else:
        scene = "夜晚"

    if weather:
        scene += f"，{weather}"

    return f"【场景】{scene}"


def build_dynamic_context(current_time_str, emotion="neutral", idle_minutes=0, character_id: int = 0):
    """构建动态上下文（每轮变化），注入用户消息头部而非 system prompt，提升缓存命中率。

    根据角色卡的 time_mode 设置决定如何注入时间信息：
    - real_time（默认）: 当前真实时间
    - none: 不注入任何时间信息（角色在无时间参照的世界里）
    - fixed: 使用角色卡设定的固定时间
    - relative: 基于角色创建时间的偏移
    """
    # ─── 读取角色卡时间模式 ───
    time_mode = "real_time"  # 默认
    fixed_time = None
    try:
        from core.character_card import CharacterCard
        card = CharacterCard.load_from_db(character_id)
        if card:
            card_data = card.card_data if hasattr(card, 'card_data') else {}
            if isinstance(card_data, dict):
                time_mode = card_data.get("time_mode", "real_time") or "real_time"
                fixed_time = card_data.get("time_fixed_at", None) if time_mode == "fixed" else None
    except Exception:
        pass

    effective_time_str = current_time_str
    effective_hour = None

    if time_mode == "none":
        # 不注入任何时间信息
        effective_time_str = ""
    elif time_mode == "fixed" and fixed_time:
        effective_time_str = fixed_time
    elif time_mode == "relative":
        # 角色创建为起点，按真实时间偏移（暂用真实时间）
        pass  # 目前 fallback 到 real_time，未来可丰富
    # real_time: 直接用 current_time_str

    emotion_info = f"用户心情{'很好' if emotion=='positive' else '不太好' if emotion=='negative' else '一般'}。"
    # 如果 time_mode=none，跳过所有时间相关描述
    if time_mode == "none":
        time_info = ""
        time_behavior = ""
        scene_atmosphere = ""
    else:
        time_info = f"现在是{effective_time_str}。"
        time_behavior = _get_time_behavior_hint()
        scene_atmosphere = _get_scene_atmosphere()

    # 关系状态每次都注入（重要，AI 需要知道当前该亲近还是保持距离）
    try:
        relationship_hint = get_relationship_hint(character_id=character_id)
    except Exception as e:
        logger.warning(f"[prompt] 关系提示获取失败: {e}")
        relationship_hint = ""
    # 关系深度指令（每 10 条注入一次）
    intimacy_hint = ""
    try:
        msg_count = get_msg_counter()
        if msg_count % 10 == 0:
            from core.relationship import get_intimacy_instruction
            intimacy_hint = get_intimacy_instruction(character_id=character_id)
    except Exception as e:
        logger.warning(f"[prompt] 亲密指令获取失败: {e}")
    # 情感行为提示每 20 轮注入一次（变化慢，省 token）
    try:
        msg_count = get_msg_counter()
    except Exception as e:
        logger.warning(f"[prompt] 消息计数获取失败: {e}")
        msg_count = 0
    emotion_behavior = ""
    if msg_count % 20 == 0:
        try:
            emotion_behavior = get_emotion_behavior_hint(character_id=character_id)
        except Exception as e:
            silent_exc("build_dynamic_context", e)
    # 感知用户离开时长（爱语方案）：超过 3 分钟未回复时注入
    absence_note = ""
    if idle_minutes > 3:
        if idle_minutes < 60:
            absence_note = f"（对方{int(idle_minutes)}分钟没回复了）"
        else:
            hours = int(idle_minutes / 60)
            mins = int(idle_minutes % 60)
            if mins > 0:
                absence_note = f"（对方{hours}小时{mins}分钟没回复了）"
            else:
                absence_note = f"（对方{hours}小时没回复了）"
    parts = [p for p in [relationship_hint, intimacy_hint, emotion_behavior, f"{time_info}{emotion_info}", time_behavior, scene_atmosphere, absence_note] if p]
    return "\n".join(parts)


# ─── SystemPromptBuilder 类（模块化接口）───

class SystemPromptBuilder:
    """
    System Prompt 模块化构建器（可选接口，不替代现有 build_system_prompt）

    通过 modules_enabled 控制各部分开关，方便按需调整 prompt 组成。
    动态组件（continuity / user_summary / plan_todo 等）已接入开关。
    静态前缀（iron_rule / fact_rule / chat_rule / identity / tools）始终注入，不受开关控制。

    用法:
        builder = SystemPromptBuilder()
        builder.modules_enabled["quirks"] = False  # 关闭随机口癖
        static, dynamic = builder.build(...)
    """

    def __init__(self):
        self.modules_enabled = {
            "iron_rule": True,         # 铁律
            "fact_rule": True,         # 事实规则
            "chat_rule": True,         # 聊天规则
            "identity": True,          # 身份信息
            "tools": True,             # 工具说明
            "thinking": "auto",        # 思考格式（auto=长消息自动, True=总是, False=从不）
            "persona": True,           # 人设
            "user_summary": True,      # 用户摘要（每20条）
            "plan_todo": True,         # 计划/待办（每20条）
            "work_memory": True,       # 工作记忆（每20条）
            "onboarding": True,        # 入职引导（首次）
            "rolling_summary": True,   # 滚动摘要（每20条）
            "summaries": True,         # 三级摘要
            "rag": True,               # 向量检索
            "entity": True,            # 实体关联
            "schedule": True,          # 日程
            "knowledge_base": True,    # 关键词触发知识
            "knowledge_graph": True,   # 知识图谱
            "time_background": True,   # 时段背景
            "continuity": True,        # 对话连续感
            "quirks": True,            # 随机口癖（5%）
            "patterns": True,          # 用户模式
            "dropped_context": True,   # 被裁掉的早期对话
            "depth_hint": True,        # 深度提示
            "post_history": True,      # 生成前指令
            "user_persona": True,     # 用户身份
        }

    def build(self, current_time_str, emotion="neutral", user_message="",
              rag_context="", summary="", keypoints=None, custom_context="",
              tiered_summaries=None, user_patterns=None, sentence_mode="auto",
              chat_history=None):
        """构建 system prompt，返回 (static_prefix, dynamic_content, depth_entries)"""
        return build_system_prompt(
            current_time_str=current_time_str,
            emotion=emotion,
            user_message=user_message,
            rag_context=rag_context,
            summary=summary,
            keypoints=keypoints,
            custom_context=custom_context,
            tiered_summaries=tiered_summaries,
            user_patterns=user_patterns,
            sentence_mode=sentence_mode,
            modules_enabled=self.modules_enabled,
            chat_history=chat_history,
        )
