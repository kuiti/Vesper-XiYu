import json
import os
import random
import requests
from datetime import datetime
from core.db import get_config, get_memory

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

def generate_greeting():
    """生成欢迎语"""
    api_key = get_config("api_key", "")
    if not api_key:
        return "欢迎回来～"
    
    hours_gone = get_time_gap_hours()
    if hours_gone is None or hours_gone < 0.5:
        return None
    
    # 获取性格和记忆
    personality = get_config("personality", {"tone": "冷静"})
    memory = get_memory()
    
    # 构建时间描述
    if hours_gone > 48:
        time_desc = f"已经{int(hours_gone)}小时（约{int(hours_gone/24)}天）没见了"
    elif hours_gone > 24:
        time_desc = f"一天多没见了（{int(hours_gone)}小时）"
    elif hours_gone > 6:
        time_desc = f"离开了{int(hours_gone)}小时"
    else:
        time_desc = f"离开了{int(hours_gone)}小时"
    
    # 获取记忆文本
    memory_text = ""
    recent = list(memory.items())[-3:] if memory else []
    if recent:
        memory_text = "你之前告诉过我：" + "；".join([f"{k}是{v}" for k, v in recent])
    
    # 获取规则
    length_level = get_config("length_level", "短")
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
        personality_part = f"你是Vesper，一个{tone}的AI助手。{length_rule}。"
    
    system_prompt = f"{length_rule}\n{personality_part}\n{memory_text}\n用户{time_desc}。请生成一个简短、自然的欢迎语。直接输出欢迎语。"
    
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "system", "content": system_prompt}],
        "temperature": 0.7,
        "max_tokens": 100
    }
    try:
        resp = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except:
        return "回来啦。"

def generate_tease():
    """生成调侃回复（用户说“我回来了”时）"""
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
    
    length_level = get_config("length_level", "短")
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
        personality_part = f"你是Vesper，一个{tone}的AI助手。{length_rule}。"
    
    system_prompt = f"{length_rule}\n{personality_part}\n{memory_text}\n用户{time_desc}，说“我回来了”。请用略带调侃但友好的语气回复一句话。直接输出回复。"
    
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "system", "content": system_prompt}],
        "temperature": 0.8,
        "max_tokens": 100
    }
    try:
        resp = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except:
        return "你还知道回来？"