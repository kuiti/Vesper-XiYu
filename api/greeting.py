import json
import os
import random
import requests
from datetime import datetime
from core.db import get_config, get_memory, get_last_user_messages

LAST_CHAT_FILE = "data/last_chat.json"
LAST_WELCOME_FILE = "data/last_welcome.json"

def load_last_chat_time():
    """加载上次聊天时间"""
    if os.path.exists(LAST_CHAT_FILE):
        with open(LAST_CHAT_FILE, 'r', encoding='utf-8') as f:
            return datetime.fromisoformat(json.load(f).get("last_time", "2000-01-01T00:00:00"))
    return None

def save_last_chat_time():
    """保存当前聊天时间"""
    with open(LAST_CHAT_FILE, 'w', encoding='utf-8') as f:
        json.dump({"last_time": datetime.now().isoformat()}, f)

def load_last_welcome():
    """加载上次欢迎时间"""
    if os.path.exists(LAST_WELCOME_FILE):
        with open(LAST_WELCOME_FILE, 'r', encoding='utf-8') as f:
            return datetime.fromisoformat(json.load(f).get("last_welcome", "2000-01-01T00:00:00"))
    return None

def save_last_welcome():
    """保存当前欢迎时间"""
    with open(LAST_WELCOME_FILE, 'w', encoding='utf-8') as f:
        json.dump({"last_welcome": datetime.now().isoformat()}, f)

def get_time_gap_hours():
    """获取距离上次聊天的小时数"""
    last = load_last_chat_time()
    if last is None:
        return None
    return (datetime.now() - last).total_seconds() / 3600

# ─── 对话尾巴：关键词匹配 ───
CONTEXT_KEYWORDS = [
    {"keywords": ["晚安", "睡觉", "睡了", "去睡", "困了", "先睡"],
     "response": "早，昨晚睡得好吗？"},
    {"keywords": ["累", "疲惫", "加班", "好累", "太累", "累死", "熬夜", "通宵"],
     "response": "休息得怎么样？今天还累吗？"},
    {"keywords": ["难过", "伤心", "哭", "崩溃", "受不了", "压力大", "焦虑"],
     "response": "心情好些了吗？"},
    {"keywords": ["开心", "高兴", "好事", "成功", "通过", "中了", "升职", "加薪"],
     "response": "昨天的开心延续到今天了吗？"},
    {"keywords": ["感冒", "发烧", "头疼", "肚子疼", "不舒服", "生病"],
     "response": "身体好些了吗？"},
    {"keywords": ["面试", "考试", "笔试", "口试", "答辩", "复试"], "response": None},
    {"keywords": ["出去玩", "旅游", "旅行", "出差", "出发"], "response": None},
    {"keywords": ["明天", "下周", "待会"], "response": None},
]

def match_conversation_context():
    """分析最近用户消息，返回上下文问候语。无匹配返回 None。"""
    messages = get_last_user_messages(3)
    if not messages:
        return None
    combined = " ".join([m["content"] for m in messages])
    for rule in CONTEXT_KEYWORDS:
        for kw in rule["keywords"]:
            if kw in combined:
                if rule["response"]:
                    return rule["response"]
                if kw in ["面试", "考试", "笔试", "口试", "答辩", "复试"]:
                    return f"{kw}怎么样了？"
                if kw in ["出去玩", "旅游", "旅行", "出差", "出发"]:
                    return "回来啦？玩得开心吗？"
                if kw in ["明天", "下周", "待会"]:
                    for m in messages:
                        if kw in m["content"]:
                            idx = m["content"].find(kw)
                            desc = m["content"][idx:idx+20].strip()
                            if len(desc) > len(kw):
                                return f"昨天说的{desc[:15]}，怎么样了？"
                    return None
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

    # 上下文感知问候：优先于 LLM 生成
    context_greeting = match_conversation_context()
    if context_greeting:
        return context_greeting

    # 获取性格和记忆
    personality = get_config("personality", {"tone": "冷静"})
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
        "详细": "每句话不超过80个字"
    }
    length_rule = length_map.get(length_level, "每句话不超过10个字")

    # 获取自定义提示词
    custom_prompt = get_config("custom_system_prompt", "")
    if custom_prompt:
        personality_part = custom_prompt
    else:
        tone = personality.get("tone", "冷静")
        personality_part = f"你是夕语，一个{tone}的AI助手。{length_rule}。"

    system_prompt = f"{length_rule}\n{personality_part}\n{memory_text}\n用户{time_desc}。\n时间风格：{slot['style']}。请生成一个简短、自然的欢迎语。直接输出欢迎语。"
    
    base_url = get_config("api_base_url", "https://api.deepseek.com/v1").rstrip("/")
    model = get_config("api_model", "deepseek-chat")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}],
        "temperature": 0.7,
        "max_tokens": 100
    }
    try:
        resp = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[问候] 异常: {e}")
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
        "详细": "每句话不超过80个字"
    }
    length_rule = length_map.get(length_level, "每句话不超过10个字")

    custom_prompt = get_config("custom_system_prompt", "")
    if custom_prompt:
        personality_part = custom_prompt
    else:
        tone = personality.get("tone", "冷静")
        personality_part = f"你是夕语，一个{tone}的AI助手。{length_rule}。"

    system_prompt = f"{length_rule}\n{personality_part}\n{memory_text}\n用户{time_desc}，说\"我回来了\"。请用略带调侃但友好的语气回复一句话。直接输出回复。"
    
    base_url = get_config("api_base_url", "https://api.deepseek.com/v1").rstrip("/")
    model = get_config("api_model", "deepseek-chat")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}],
        "temperature": 0.8,
        "max_tokens": 100
    }
    try:
        resp = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[问候] 异常: {e}")
        return "你还知道回来？"


def generate_proactive(idle_minutes: int):
    """根据空闲时长、时间、情绪、关系、提醒生成智能主动问候"""
    api_key = get_config("api_key", "")
    if not api_key:
        return None

    # ─── 时间感知：深夜不打扰（23:00-7:00） ───
    now = datetime.now()
    hour = now.hour
    if 23 <= hour or hour < 7:
        return None

    # ─── 获取基础信息 ───
    personality = get_config("personality", {})
    if not isinstance(personality, dict):
        personality = {}
    tone = personality.get("tone", "冷静")
    user_name = get_config("user_name", "我")
    ai_name = get_config("ai_name", "夕语")
    hours = idle_minutes // 60

    if idle_minutes < 60:
        time_desc = f"{idle_minutes}分钟"
    else:
        time_desc = f"{hours}小时"

    custom_prompt = get_config("custom_system_prompt", "")
    if custom_prompt:
        personality_part = custom_prompt
    else:
        personality_part = f"你是{ai_name}，一个{tone}的AI助手。"

    # ─── 时间段描述（细化） ───
    if 7 <= hour < 9:
        time_context = "现在是清晨，用户可能刚起床"
    elif 9 <= hour < 12:
        time_context = "现在是上午，工作/学习时间"
    elif 12 <= hour < 14:
        time_context = "现在是中午，午饭时间"
    elif 14 <= hour < 18:
        time_context = "现在是下午"
    elif 18 <= hour < 20:
        time_context = "现在是傍晚，可能刚下班/放学"
    elif 20 <= hour < 23:
        time_context = "现在是晚上，休息时间"
    else:
        time_context = ""

    # ─── 情绪结合 ───
    try:
        from core.emotion_tracker import get_emotion_summary
        emotion_summary = get_emotion_summary()
    except Exception:
        emotion_summary = ""

    # ─── 关系结合 ───
    try:
        from core.relationship import get_relationship_hint, get_ai_emotion
        relationship_hint = get_relationship_hint()
        ai_emotion = get_ai_emotion()
        # AI 情绪消极时减少主动问候
        if ai_emotion in ["cold", "annoyed", "distrustful"]:
            if "负面" not in emotion_summary:
                return None  # AI 情绪消极 + 用户情绪正常 = 不问候
    except Exception:
        relationship_hint = ""
        ai_emotion = "neutral"

    # ─── 提醒联动 ───
    reminder_context = ""
    try:
        from core.db import get_reminders
        reminders = get_reminders()
        pending = [r for r in reminders if not r.get("done")]
        upcoming = []
        for r in pending:
            try:
                target = datetime.fromisoformat(r["target_time"])
                minutes_left = (target - now).total_seconds() / 60
                if 0 < minutes_left < 120:  # 2 小时内到期
                    upcoming.append(r)
            except Exception:
                pass
        if upcoming:
            reminder_context = f"用户有一个提醒即将到期：{upcoming[0]['content']}"
    except Exception:
        pass

    # ─── 记忆使用 ───
    memory_context = ""
    try:
        from core.db import get_memory
        memory = get_memory()
        recent = list(memory.items())[-3:] if memory else []
        if recent:
            memory_context = "你记得用户说过：" + "；".join([f"{k}是{v}" for k, v in recent])
    except Exception:
        pass

    # ─── 构建升级版 prompt ───
    prompt = f"""{personality_part}
{relationship_hint}
{time_context}。
你已经{time_desc}没收到{user_name}的消息了。
{emotion_summary}
{reminder_context}
{memory_context}

请用一句简短自然的话（10-20字），根据当前情况选择：
- 如果用户情绪不好，关心一下
- 如果有提醒即将到期，温和提醒
- 如果是早上/晚上，用合适的问候
- 否则，像朋友一样闲聊

直接说内容，别加动作描写。"""

    base_url = get_config("api_base_url", "https://api.deepseek.com/v1").rstrip("/")
    model = get_config("api_model", "deepseek-chat")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.8,
        "max_tokens": 60
    }
    try:
        resp = requests.post(f"{base_url}/chat/completions",
                             headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None