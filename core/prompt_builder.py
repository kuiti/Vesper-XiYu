# core/prompt_builder.py  |  v3.9.0
from core.db import get_config, set_config, get_conn, get_msg_counter
from core.relationship import get_relationship_hint, get_emotion_behavior_hint
from core.persona_data import (
    LENGTH_MAP, PERSONA_TEMPLATE_WITH_FOUNDATION,
    PERSONA_TEMPLATE_WITHOUT_FOUNDATION, TONE_DESCRIPTIONS,
    FOUNDATION_TEMPLATES, DEFAULT_FOUNDATION, DEFAULT_TABOOS,
)



# ─── 用户摘要指令（Zep 方案）───
# 定义关于用户的关键问题，从已有画像和事实中提取答案



def _get_user_summary() -> str:
    """从画像和事实中生成用户摘要（Zep 方案）"""
    # 收集画像
    profile_items = {}
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value, confidence FROM user_profile WHERE confidence >= 0.55 AND key NOT LIKE '_fact_%'")
        for r in cursor.fetchall():
            profile_items[r["key"]] = r["value"]
    # 收集事实
    import json as _json
    facts = []
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM user_profile WHERE key LIKE '_fact_%' ORDER BY extracted_at DESC LIMIT 20")
        for r in cursor.fetchall():
            try:
                d = _json.loads(r["value"])
                if d.get("importance", 0) >= 5:
                    facts.append(d["text"])
            except Exception:
                pass
    if not profile_items and not facts:
        return ""
    lines = []
    if profile_items:
        for k, v in list(profile_items.items())[:8]:
            lines.append(f"📝 {k}：{v}")
    if facts:
        for f in facts[:5]:
            lines.append(f"📝 {f}")
    if not lines:
        return ""
    return "【我记得关于你的事】\n" + "\n".join(lines) + "\n（自然地提起这些——像朋友记得对方的事一样，不用搞成汇报。如果用户当前话题跟这些没关系，不提也行。）"


def _get_plan_todo_context() -> str:
    """获取计划/待办上下文（LobeChat 方案）"""
    parts = []
    # 从工作记忆获取当前目标
    goal = get_config("_scratch_goal", "")
    if goal:
        parts.append(f"当前目标: {goal}")
    # 获取待办
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT task, done FROM todos ORDER BY id DESC LIMIT 5")
        todos = cursor.fetchall()
    if todos:
        todo_lines = []
        for t in todos:
            status = "✓" if t["done"] else "○"
            todo_lines.append(f"{status} {t['task']}")
        parts.append("待办:\n" + "\n".join(todo_lines))
    if not parts:
        return ""
    return "【计划与待办】\n" + "\n".join(parts)


def _get_onboarding_hint() -> str:
    """引导入职（LobeChat 方案）：首次对话时主动了解用户"""
    # 检查是否已完成入职
    onboarding_done = get_config("_onboarding_done", "")
    if onboarding_done:
        return ""
    # 检查已有画像数量
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM user_profile WHERE key NOT LIKE '_fact_%'")
        cnt = cursor.fetchone()["cnt"]
    if cnt >= 5:
        # 画像足够，标记入职完成
        set_config("_onboarding_done", "true")
        return ""
    # 入职阶段：温和引导，不主动追问隐私
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


# ─── 知识库（SillyTavern 世界书方案 + 时间效果）───
# 每个条目: {keys: [触发关键词], content: 注入内容, priority: 优先级, sticky: N轮, cooldown: M轮}
# 可通过 API 动态添加
_KNOWLEDGE_REGISTRY = []
_KNOWLEDGE_TIMED = {}  # {key: {"sticky_until": int, "cooldown_until": int}}
_KNOWLEDGE_MSG_COUNT = 0


def register_knowledge(keys: list, content: str, priority: int = 5, sticky: int = 0, cooldown: int = 0):
    """注册一个关键词触发的知识条目
    sticky: 触发后持续 N 轮（即使关键词不再出现）
    cooldown: 冷却 N 轮（防止重复触发）
    """
    _KNOWLEDGE_REGISTRY.append({
        "keys": [k.lower() for k in keys],
        "content": content,
        "priority": priority,
        "sticky": sticky,
        "cooldown": cooldown,
    })


def _get_triggered_knowledge(user_message: str, max_tokens: int = 300) -> str:
    """根据用户消息中的关键词触发知识注入（带时间效果）"""
    global _KNOWLEDGE_MSG_COUNT
    if not _KNOWLEDGE_REGISTRY or not user_message:
        return ""
    _KNOWLEDGE_MSG_COUNT += 1
    msg_lower = user_message.lower() if user_message else ""
    triggered = []
    for entry in _KNOWLEDGE_REGISTRY:
        entry_key = "|".join(entry["keys"])
        timed = _KNOWLEDGE_TIMED.get(entry_key, {})
        # 检查冷却
        if timed.get("cooldown_until", 0) > _KNOWLEDGE_MSG_COUNT:
            continue
        # 检查粘性（即使关键词不匹配也激活）
        is_sticky = timed.get("sticky_until", 0) > _KNOWLEDGE_MSG_COUNT
        # 关键词匹配
        is_match = any(key in msg_lower for key in entry["keys"])
        if is_match or is_sticky:
            triggered.append(entry)
            # 更新时间效果
            new_timed = {}
            if is_match and entry.get("sticky", 0) > 0:
                new_timed["sticky_until"] = _KNOWLEDGE_MSG_COUNT + entry["sticky"]
            if is_match and entry.get("cooldown", 0) > 0:
                new_timed["cooldown_until"] = _KNOWLEDGE_MSG_COUNT + entry["cooldown"]
            if new_timed:
                _KNOWLEDGE_TIMED[entry_key] = {**timed, **new_timed}
    if not triggered:
        return ""
    # 按优先级排序，取前 N 条（受令牌预算限制）
    triggered.sort(key=lambda x: -x["priority"])
    result = []
    total_len = 0
    for entry in triggered:
        if total_len + len(entry["content"]) > max_tokens * 4:  # 粗略估算 1 token ≈ 4 字符
            break
        result.append(entry["content"])
        total_len += len(entry["content"])
    if not result:
        return ""
    return "【相关知识】\n" + "\n".join(result)


# 预置知识条目
register_knowledge(
    keys=["生日", "birthday"],
    content="用户提到生日时，注意记录日期，并在临近时主动提醒。生日是重要的情感节点。",
    priority=8,
)
register_knowledge(
    keys=["考试", "面试", "exam", "interview"],
    content="用户提到考试或面试时，这是高压力事件。给予支持和鼓励，不要施加额外压力。",
    priority=7,
)
register_knowledge(
    keys=["难过", "伤心", "委屈", "哭"],
    content="用户情绪低落时，先接住情绪（'嗯，我听到了'），不要急于给建议。陪伴比解决方案更重要。",
    priority=9,
)


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


def clear_persona_cache():
    """清除人设缓存（切换角色卡后调用）"""
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

    # 计算配置 hash，内容不变时返回缓存
    config_key = f"{ai_name}|{tone}|{length_level}|{recall_past}|{allow_emotion}|{custom_prompt}|{ai_bg}"
    current_hash = hash(config_key)
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
    user_taboos = bg_obj.get("taboos", [])
    all_taboos = DEFAULT_TABOOS + user_taboos
    taboos_text = "\n".join(f"- {t}" for t in all_taboos)

    # 关系描述
    relationship_desc = bg_obj.get("role", "朋友")

    # 自定义 prompt 优先（替换人设中的名字为 ai_name，避免冲突）
    if custom_prompt and custom_prompt.strip():
        import re as _re
        _prompt = custom_prompt.strip()
        # 从人设中提取角色名（"你是XXX"开头），替换为 ai_name
        _name_match = _re.match(r'^你是[（(]?([^，。,.\s）)]+)', _prompt)
        if _name_match:
            _char_name = _name_match.group(1)
            if _char_name != ai_name:
                _prompt = _prompt.replace(f"你是{_char_name}", f"你是「{ai_name}」", 1)
                # 后续出现的角色名也替换
                _prompt = _prompt.replace(_char_name, ai_name)
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
        if foundation:
            persona = PERSONA_TEMPLATE_WITH_FOUNDATION.format(
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
        else:
            persona = PERSONA_TEMPLATE_WITHOUT_FOUNDATION.format(
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


def _get_continuity_bridge() -> str:
    """生成对话连续感提示——让 AI 感觉是在延续对话，而非每次重新开始"""
    from datetime import datetime as _dt
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            # 获取最后一条用户消息和 AI 回复
            cursor.execute(
                "SELECT role, content, timestamp FROM chat_history ORDER BY id DESC LIMIT 6"
            )
            recent = list(reversed(cursor.fetchall()))
    except Exception:
        return ""
    if not recent:
        return ""
    # 计算时间差
    try:
        last_ts = _dt.fromisoformat(recent[-1]["timestamp"])
        gap_minutes = (_dt.now() - last_ts).total_seconds() / 60
    except Exception:
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
    parts = [f"这是你们今天第N次聊天了——不要像第一次见面一样客气。"]
    parts.append(f"上次聊了{gap_desc}前，用户最后说的是：「{last_topic}」。")
    parts.append(f"自然承接上次的话题和情绪，像朋友之间继续聊天一样，不需要重新打招呼。")
    parts.append(f"如果用户没主动提上次的事，你也不需要刻意提——但要保持和之前一致的亲近感和态度。")
    return "【对话连续感——重要】" + " ".join(parts)


def build_system_prompt(current_time_str, emotion="neutral", user_message="", rag_context="", summary="", keypoints=None, custom_context="", tiered_summaries=None, user_patterns=None, sentence_mode="auto", modules_enabled=None):
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
    )

    pipeline = get_default_pipeline()
    static_prefix, dynamic_content = pipeline.build(ctx)

    # ─── 分隔符分句指令 ───
    if sentence_mode == "delimiter":
        dynamic_content += "\n【分隔符规则——最高优先级】你必须在每句话结束时插入 <<>>（四个字符：两个小于号两个大于号）然后再继续下一句。这不是可选的——每个自然句结尾都必须有 <<>>。示例：今天天气真好<<>>适合出门走走<<>>你想去哪？"

    # 返回 (可缓存的静态前缀, 每次变化的动态内容)
    return static_prefix, dynamic_content


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


def build_dynamic_context(current_time_str, emotion="neutral", idle_minutes=0):
    """构建动态上下文（每轮变化），注入用户消息头部而非 system prompt，提升缓存命中率"""
    time_info = f"现在是{current_time_str}。"
    emotion_info = f"用户心情{'很好' if emotion=='positive' else '不太好' if emotion=='negative' else '一般'}。"
    time_behavior = _get_time_behavior_hint()
    # 关系状态每次都注入（重要，AI 需要知道当前该亲近还是保持距离）
    try:
        relationship_hint = get_relationship_hint()
    except Exception:
        relationship_hint = ""
    # 情感行为提示每 20 轮注入一次（变化慢，省 token）
    try:
        msg_count = get_msg_counter()
    except Exception:
        msg_count = 0
    emotion_behavior = ""
    if msg_count % 20 == 0:
        try:
            emotion_behavior = get_emotion_behavior_hint()
        except Exception:
            pass
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
    parts = [p for p in [relationship_hint, emotion_behavior, f"{time_info}{emotion_info}", time_behavior, absence_note] if p]
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
        }

    def build(self, current_time_str, emotion="neutral", user_message="",
              rag_context="", summary="", keypoints=None, custom_context="",
              tiered_summaries=None, user_patterns=None, sentence_mode="auto"):
        """构建 system prompt，返回 (static_prefix, dynamic_content)"""
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
        )
