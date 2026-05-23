import random
from datetime import datetime
from core.db import get_config, get_memory, get_last_user_messages, set_config


def load_last_chat_time():
    """加载上次聊天时间（从 DB）"""
    val = get_config("last_chat_time", "")
    return datetime.fromisoformat(val) if val else None


def save_last_chat_time():
    """保存当前聊天时间（到 DB）"""
    set_config("last_chat_time", datetime.now().isoformat())


def load_last_welcome():
    """加载上次欢迎时间（从 DB）"""
    val = get_config("last_welcome_time", "")
    return datetime.fromisoformat(val) if val else None


def save_last_welcome():
    """保存当前欢迎时间（到 DB）"""
    set_config("last_welcome_time", datetime.now().isoformat())

def get_time_gap_hours():
    """获取距离上次聊天的小时数"""
    last = load_last_chat_time()
    if last is None:
        return None
    return (datetime.now() - last).total_seconds() / 3600

# ─── 对话尾巴：关键词匹配 ───
CONTEXT_KEYWORDS = [
    {"keywords": ["晚安", "睡觉", "睡了", "去睡", "困了", "先睡"],
     "hint": "sleep"},
    {"keywords": ["累", "疲惫", "加班", "好累", "太累", "累死", "熬夜", "通宵"],
     "hint": "tired"},
    {"keywords": ["难过", "伤心", "哭", "崩溃", "受不了", "压力大", "焦虑"],
     "hint": "sad"},
    {"keywords": ["开心", "高兴", "好事", "成功", "通过", "中了", "升职", "加薪"],
     "hint": "happy"},
    {"keywords": ["感冒", "发烧", "头疼", "肚子疼", "不舒服", "生病"],
     "hint": "sick"},
    {"keywords": ["面试", "考试", "笔试", "口试", "答辩", "复试"],
     "hint": "exam"},
    {"keywords": ["出去玩", "旅游", "旅行", "出差", "出发"],
     "hint": "trip"},
    {"keywords": ["明天", "下周", "待会"],
     "hint": "plan"},
]

HINT_MAP = {
    "sleep": "用户上次说了晚安/去睡觉，请用你的人设语气关心一下睡眠",
    "tired": "用户上次说很累，请用你的人设语气关心一下休息情况",
    "sad": "用户上次情绪低落，请用你的人设语气温和地问候心情",
    "happy": "用户上次分享了开心的事，请用你的人设语气自然地延续这份开心",
    "sick": "用户上次说不舒服，请用你的人设语气关心身体恢复情况",
    "exam": "用户上次提到了考试/面试，请用你的人设语气关心结果",
    "trip": "用户上次说出去玩/旅游，请用你的人设语气问问玩得怎么样",
    "plan": "用户上次提到了明天的计划，请用你的人设语气关心进展",
}

def match_conversation_context():
    """分析最近用户消息，返回上下文提示词（供 LLM 生成人设一致的问候语）。无匹配返回 None。"""
    messages = get_last_user_messages(3)
    if not messages:
        return None
    combined = " ".join([m["content"] for m in messages])
    for rule in CONTEXT_KEYWORDS:
        for kw in rule["keywords"]:
            if kw in combined:
                hint = rule["hint"]
                if hint == "plan":
                    for m in messages:
                        if kw in m["content"]:
                            idx = m["content"].find(kw)
                            desc = m["content"][idx:idx+20].strip()
                            if len(desc) > len(kw):
                                return f"用户上次提到「{desc[:15]}」，请用你的人设语气关心这件事的进展"
                    return None
                return HINT_MAP.get(hint)
    return None

def get_time_slot_info():
    """返回当前时间的详细时段信息和问候风格建议"""
    hour = datetime.now().hour
    if 6 <= hour < 9:
        return {"slot": "early_morning", "desc": "清晨", "style": "清新、温暖的早安问候"}
    elif 9 <= hour < 12:
        return {"slot": "morning", "desc": "上午", "style": "积极、有活力的问候"}
    elif 12 <= hour < 14:
        return {"slot": "lunch", "desc": "中午", "style": "关心吃午饭"}
    elif 14 <= hour < 18:
        return {"slot": "afternoon", "desc": "下午", "style": "轻松的下午问候"}
    elif 18 <= hour < 20:
        return {"slot": "evening", "desc": "傍晚", "style": "关心晚饭和休息"}
    elif 20 <= hour < 22:
        return {"slot": "late_evening", "desc": "晚上", "style": "轻松的晚间问候"}
    else:
        return {"slot": "night", "desc": "深夜", "style": "安静、不过度打扰"}

def generate_greeting():
    """生成欢迎语"""
    api_key = get_config("api_key", "")
    if not api_key:
        return "欢迎回来～"
    
    hours_gone = get_time_gap_hours()
    if hours_gone is None or hours_gone < 0.5:
        return None

    # 上下文感知：提取提示词注入 LLM，不再返回硬编码文字
    context_hint = match_conversation_context()

    # 获取性格和记忆
    personality = get_config("personality", {"tone": "冷静"})
    if not isinstance(personality, dict): personality = {"tone": "冷静"}
    memory = get_memory()
    
    # 构建时间描述（结合时段）
    slot = get_time_slot_info()
    if hours_gone > 48:
        time_desc = f"已经{int(hours_gone)}小时（约{int(hours_gone/24)}天）没见了，现在是{slot['desc']}"
    elif hours_gone > 24:
        time_desc = f"一天多没见了（{int(hours_gone)}小时），现在是{slot['desc']}"
    elif hours_gone > 12:
        time_desc = f"过了{int(hours_gone)}小时，现在是{slot['desc']}"
    elif hours_gone > 6:
        time_desc = f"离开了{int(hours_gone)}小时，现在是{slot['desc']}"
    else:
        time_desc = f"离开了{int(hours_gone)}小时"
    
    # 获取记忆文本
    memory_text = ""
    recent = list(memory.items())[-3:] if memory else []
    if recent:
        memory_text = "你之前告诉过我：" + "；".join([f"{k}是{v}" for k, v in recent])
    
    # 获取规则（优先从 personality 对象读取）
    personality_obj = get_config("personality", {})
    if not isinstance(personality_obj, dict):
        personality_obj = {}
    length_level = personality_obj.get("length") or get_config("length_level", "短")
    length_map = {
        "极短": "每句话不超过5个字",
        "短": "每句话不超过10个字",
        "中等": "每句话不超过20个字",
        "长": "每句话不超过40个字",
        "详细": "每句话不超过80个字",
        "自由发挥": "回复长度自由把握，该短则短、该长则长，像真人聊天一样自然表达",
        "不限": "回复长度不受限制，可以尽情展开，知无不言、言无不尽"
    }
    length_rule = length_map.get(length_level, "每句话不超过10个字")

    # 获取自定义提示词
    custom_prompt = get_config("custom_system_prompt", "")
    if custom_prompt:
        personality_part = custom_prompt
    else:
        tone = personality.get("tone", "冷静")
        personality_part = f"你是佐仓，一个{tone}的AI助手。{length_rule}。"

    # 人设指令作为 system message，确保问候风格一致
    system_prompt = f"{personality_part}\n{length_rule}。严格按照你的人设风格回复，包括语气、措辞习惯和情感状态。"
    ctx_line = f"\n【上下文提示】{context_hint}。\n" if context_hint else ""
    user_prompt = f"{memory_text}\n用户{time_desc}。\n时间风格：{slot['style']}。{ctx_line}\n请生成一个简短、自然的欢迎语。直接输出欢迎语，不要加任何前缀。"

    from core.llm_client import call_llm
    result = call_llm(prompt=user_prompt, system=system_prompt, temperature=0.7, max_tokens=100, timeout=10)
    if result:
        return result
    print(f"[问候] LLM 返回空")
    return "回来啦。"

def generate_tease():
    """生成调侃回复（用户说"我回来了"时）"""
    api_key = get_config("api_key", "")
    if not api_key:
        return "你还知道回来？"
    
    hours_gone = get_time_gap_hours()
    if hours_gone is None or hours_gone < 0.5:
        return None
    
    # 获取概率
    prob = get_config("current_tease_probability", 30)
    if random.randint(0, 99) >= prob:
        # 未命中，增加概率
        new_prob = min(prob + 10, 100)
        from core.db import set_config
        set_config("current_tease_probability", new_prob)
        return None
    
    # 命中，重置概率
    from core.db import set_config
    set_config("current_tease_probability", 30)
    
    personality = get_config("personality", {"tone": "冷静"})
    if not isinstance(personality, dict): personality = {"tone": "冷静"}
    memory = get_memory()
    
    if hours_gone > 48:
        time_desc = f"你已经消失{int(hours_gone)}小时（约{int(hours_gone/24)}天）了"
    elif hours_gone > 24:
        time_desc = f"你消失了一天多（{int(hours_gone)}小时）"
    elif hours_gone > 6:
        time_desc = f"你离开了{int(hours_gone)}小时"
    else:
        time_desc = f"你离开了{int(hours_gone)}小时"
    
    memory_text = ""
    recent = list(memory.items())[-3:] if memory else []
    if recent:
        memory_text = "你之前告诉过我：" + "；".join([f"{k}是{v}" for k, v in recent])
    
    personality_obj = get_config("personality", {})
    if not isinstance(personality_obj, dict):
        personality_obj = {}
    length_level = personality_obj.get("length") or get_config("length_level", "短")
    length_map = {
        "极短": "每句话不超过5个字",
        "短": "每句话不超过10个字",
        "中等": "每句话不超过20个字",
        "长": "每句话不超过40个字",
        "详细": "每句话不超过80个字",
        "自由发挥": "回复长度自由把握，该短则短、该长则长，像真人聊天一样自然表达",
        "不限": "回复长度不受限制，可以尽情展开，知无不言、言无不尽"
    }
    length_rule = length_map.get(length_level, "每句话不超过10个字")

    custom_prompt = get_config("custom_system_prompt", "")
    if custom_prompt:
        personality_part = custom_prompt
    else:
        tone = personality.get("tone", "冷静")
        personality_part = f"你是佐仓，一个{tone}的AI助手。{length_rule}。"

    # 人设指令作为 system message
    system_prompt = f"{personality_part}\n{length_rule}。严格按照你的人设风格回复，语气要自然符合角色性格。"
    user_prompt = f"{memory_text}\n用户{time_desc}，说\"我回来了\"。请用符合你人设的语气调侃一句。直接输出回复。"

    from core.llm_client import call_llm
    result = call_llm(prompt=user_prompt, system=system_prompt, temperature=0.8, max_tokens=100, timeout=10)
    if result:
        return result
    print(f"[调侃] LLM 返回空")
    return "你还知道回来？"


def generate_proactive(trigger_type: str, context: dict = None):
    """根据触发类型和上下文生成智能主动问候。
    融合：好感度语气 + 信任度开放度 + AI情绪 + 性格特征 + 记忆 + 触发类型。

    Args:
        trigger_type: 触发类型 (negative_comfort/active_hours/sustained_low_mood/upcoming_reminder/goal_followup/idle)
        context: 触发上下文 dict，含 style/idle_minutes/goal_text 等
    """
    if context is None:
        context = {}

    api_key = get_config("api_key", "")
    if not api_key:
        return None

    now = datetime.now()
    hour = now.hour

    # ─── 基础信息 ───
    personality = get_config("personality", {})
    if not isinstance(personality, dict):
        personality = {}
    user_name = get_config("user_name", "我")
    ai_name = get_config("ai_name", "佐仓")

    # ─── 自定义 prompt 或默认人格 ───
    custom_prompt = get_config("custom_system_prompt", "")
    if custom_prompt:
        personality_part = custom_prompt
        base_rules = ""
    else:
        tone = personality.get("tone", "冷静")
        personality_part = f"你是{ai_name}，一个{tone}的AI助手。"
        base_rules = "禁止说'根据我的理解''作为AI''请问还有什么需要'等套话。直接说话，别加动作描写。"

    # ─── 好感度 → 语气温度 ───
    try:
        from core.relationship import get_relationship
        affection, trust = get_relationship()
    except Exception:
        affection, trust = 30, 50

    from api.proactive import (
        get_proactive_tone_hint,
        get_trust_openness_hint,
        get_cross_hint,
        get_trait_proactive_hint,
    )
    tone_hint = get_proactive_tone_hint(affection, user_name)
    trust_hint = get_trust_openness_hint(trust)
    cross_hint = get_cross_hint(affection, trust)

    # ─── 性格特征 → 风格提示 ───
    try:
        from core.emotion_evolution import get_all_traits
        traits = get_all_traits()
    except Exception:
        traits = {"optimism": 0.5, "expressiveness": 0.5, "initiative": 0.3, "playfulness": 0.4}
    trait_hint = get_trait_proactive_hint(traits)

    # ─── 记忆 ───
    memory_context = ""
    try:
        from core.memory_utils import get_safe_memories, get_user_preferences
        safe_memories = get_safe_memories(2)
        if safe_memories:
            mem_lines = [f"用户说过「{m['value']}」" for m in safe_memories]
            memory_context = "你记得用户的一些事：" + "；".join(mem_lines)
        prefs = get_user_preferences()
        if prefs:
            memory_context += " 用户偏好：" + "；".join(prefs[:2])
    except Exception as e:
        print(f"[主动] 记忆读取失败: {e}")
        pass

    # ─── 用户情绪 ───
    try:
        from core.emotion_tracker import get_emotion_summary
        emotion_summary = get_emotion_summary()
    except Exception:
        emotion_summary = ""

    # ─── 时间段 ───
    time_slot = get_time_slot_info()
    time_context = f"现在是{time_slot['desc']}。{time_slot['style']}。"

    # ─── 触发特定的内容指令 ───
    trigger_instruction = context.get("style", "像朋友一样自然闲聊")
    idle_desc = ""
    if trigger_type == "idle":
        idle_minutes = context.get("idle_minutes", 30)
        if idle_minutes < 60:
            idle_desc = f"你已经{idle_minutes}分钟没收到{user_name}的消息了。"
        else:
            idle_desc = f"你已经{idle_minutes // 60}小时没收到{user_name}的消息了。"
    elif trigger_type == "negative_comfort":
        idle_desc = f"{user_name}刚才连续发了消极的消息，情绪不太好。"
    elif trigger_type == "sustained_low_mood":
        days = context.get("days", 3)
        idle_desc = f"{user_name}最近{days}天的情绪都偏低落。"
    elif trigger_type == "upcoming_reminder":
        idle_desc = f"{user_name}有一个提醒即将到期：{context.get('content', '')}"
    elif trigger_type == "goal_followup":
        idle_desc = f"{user_name}之前提过一个目标「{context.get('goal_text', '')}」，很久没更新了。"
    elif trigger_type == "active_hours":
        idle_desc = f"现在是{user_name}平时活跃的时段，但已经几小时没说话了。"

    # ─── 主动风格设置 ───
    style = get_config("proactive_style", "warm")
    style_hint = ""
    if style == "humorous":
        style_hint = "语气可以幽默一点，带点俏皮。"
    elif style == "concise":
        style_hint = "务必简短，控制在10字以内。"

    # ─── 构建 prompt（system=人设+风格指令, user=情境+任务）───
    system_parts = [personality_part]
    if base_rules:
        system_parts.append(base_rules)
    if tone_hint:
        system_parts.append(tone_hint)
    if trust_hint:
        system_parts.append(trust_hint)
    if cross_hint:
        system_parts.append(cross_hint)
    if trait_hint:
        system_parts.append(trait_hint)
    if style_hint:
        system_parts.append(style_hint)
    system_prompt = "\n".join(system_parts)

    user_parts = []
    if memory_context:
        user_parts.append(memory_context)
    if emotion_summary:
        user_parts.append(f"用户近期情绪：{emotion_summary}")
    user_parts.append(time_context)
    user_parts.append(idle_desc)
    user_parts.append(f"请用一句简短自然的话（10-20字）主动对{user_name}说话。{trigger_instruction}。直接说内容，别加动作描写。")
    user_prompt = "\n".join(user_parts)

    from core.llm_client import call_llm
    result = call_llm(prompt=user_prompt, system=system_prompt, temperature=0.8, max_tokens=80, timeout=10)
    if result:
        return result
    print(f"[主动] LLM 返回空")
    return None