# core/reminder_ai.py — 温和通知内容生成
"""根据任务类型、紧急程度、AI 情绪生成有人情味的通知内容"""

import random
from datetime import datetime

# 任务分类关键词
CATEGORY_KEYWORDS = {
    "work": ["报告", "会议", "项目", "客户", "deadline", "交付", "汇报", "工作", "上班", "加班"],
    "health": ["吃药", "体检", "运动", "喝水", "休息", "睡觉", "锻炼", "看病", "复查"],
    "study": ["考试", "复习", "作业", "论文", "学习", "上课", "培训"],
    "personal": ["买", "取", "寄", "约", "聚会", "生日", "快递", "购物", "做饭", "打扫"],
}

# 温和风格模板
WARM_TEMPLATES = {
    "work": {
        "low": ["{content}，有空处理一下就好", "{content}，不着急，安排一下", "{content}，记得哦～"],
        "medium": ["{content}，时间快到了呢", "{content}，差不多该准备了", "{content}，提醒你一下～"],
        "high": ["{content}，不能再拖了哦", "{content}，赶紧处理一下吧", "{content}，时间紧迫！"],
    },
    "health": {
        "low": ["{content}，注意身体哦", "{content}，别太累了", "{content}，照顾好自己～"],
        "medium": ["{content}，该休息一下了", "{content}，身体最重要", "{content}，别忘了照顾自己"],
        "high": ["{content}，必须马上处理！", "{content}，健康不能等！", "{content}，赶紧的！"],
    },
    "study": {
        "low": ["{content}，有空准备一下", "{content}，不急，慢慢来", "{content}，记得安排时间～"],
        "medium": ["{content}，该开始准备了", "{content}，时间不多了哦", "{content}，加油！"],
        "high": ["{content}，不能再拖了！", "{content}，赶紧复习！", "{content}，冲刺！"],
    },
    "personal": {
        "low": ["{content}，有空的话记得一下", "{content}，不着急～", "{content}，顺便处理一下"],
        "medium": ["{content}，别忘了哦", "{content}，提醒你一下", "{content}，该处理了"],
        "high": ["{content}，赶紧去！", "{content}，不能再等了！", "{content}，快去处理！"],
    },
    "general": {
        "low": ["{content}，有空处理一下", "{content}，记得哦", "{content}，不着急～"],
        "medium": ["{content}，该处理了", "{content}，提醒你一下", "{content}，别忘了"],
        "high": ["{content}，赶紧处理！", "{content}，不能再拖了！", "{content}，马上！"],
    },
}

# 随意风格模板
CASUAL_TEMPLATES = {
    "work": {
        "low": ["{content}，记一下", "{content}，有空搞", "{content}，安排～"],
        "medium": ["{content}，该搞了", "{content}，快到了", "{content}，冲！"],
        "high": ["{content}！赶紧！", "{content}！不能再拖！", "{content}！快！"],
    },
    "health": {
        "low": ["{content}！", "{content}，注意！", "{content}，别忘！"],
        "medium": ["{content}！该了！", "{content}！必须！", "{content}！马上！"],
        "high": ["{content}！！！", "{content}！立刻！", "{content}！紧急！"],
    },
    "study": {
        "low": ["{content}，加油", "{content}，慢慢来", "{content}，可以的"],
        "medium": ["{content}！冲！", "{content}！加油！", "{content}！你可以！"],
        "high": ["{content}！！！", "{content}！拼了！", "{content}！必胜！"],
    },
    "personal": {
        "low": ["{content}，顺便", "{content}，有空搞", "{content}，记一下"],
        "medium": ["{content}！别忘！", "{content}！该了！", "{content}！冲！"],
        "high": ["{content}！赶紧！", "{content}！快！", "{content}！马上！"],
    },
    "general": {
        "low": ["{content}，记一下", "{content}，有空搞", "{content}，安排"],
        "medium": ["{content}！该了！", "{content}！别忘！", "{content}！冲！"],
        "high": ["{content}！赶紧！", "{content}！快！", "{content}！马上！"],
    },
}

# 专业风格模板
PROFESSIONAL_TEMPLATES = {
    "work": {
        "low": ["提醒：{content}", "待办：{content}", "任务：{content}"],
        "medium": ["提醒：{content}（即将到期）", "待办：{content}（时间紧迫）", "任务：{content}（需处理）"],
        "high": ["紧急：{content}", "重要：{content}（立即处理）", "优先：{content}（不可延迟）"],
    },
    "health": {
        "low": ["健康提醒：{content}", "身体提醒：{content}", "健康：{content}"],
        "medium": ["健康提醒：{content}（请及时）", "身体提醒：{content}（重要）", "健康：{content}（需关注）"],
        "high": ["紧急健康：{content}", "健康警告：{content}（立即处理）", "健康：{content}（不可忽视）"],
    },
    "study": {
        "low": ["学习提醒：{content}", "学业：{content}", "学习：{content}"],
        "medium": ["学习提醒：{content}（即将截止）", "学业：{content}（需准备）", "学习：{content}（时间紧）"],
        "high": ["紧急学业：{content}", "学业警告：{content}（立即处理）", "学业：{content}（不可延迟）"],
    },
    "personal": {
        "low": ["个人提醒：{content}", "待办：{content}", "个人：{content}"],
        "medium": ["个人提醒：{content}（别忘了）", "待办：{content}（该处理了）", "个人：{content}（提醒）"],
        "high": ["紧急个人：{content}", "个人警告：{content}（立即处理）", "个人：{content}（不可延迟）"],
    },
    "general": {
        "low": ["提醒：{content}", "待办：{content}", "任务：{content}"],
        "medium": ["提醒：{content}（即将到期）", "待办：{content}（需处理）", "任务：{content}（时间紧）"],
        "high": ["紧急：{content}", "重要：{content}（立即处理）", "优先：{content}（不可延迟）"],
    },
}

# 风格模板映射
STYLE_TEMPLATES = {
    "warm": WARM_TEMPLATES,
    "casual": CASUAL_TEMPLATES,
    "professional": PROFESSIONAL_TEMPLATES,
}


def classify_category(content: str) -> str:
    """根据内容关键词判断任务分类"""
    content_lower = content.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in content_lower for kw in keywords):
            return category
    return "general"


def get_urgency_level(level: int) -> str:
    """将 7 级提醒转换为 3 级紧急程度"""
    if level >= 6:
        return "high"
    elif level >= 4:
        return "medium"
    else:
        return "low"


def generate_reminder_message(content: str, level: int, style: str = "warm", category: str = None) -> str:
    """生成温和的通知内容

    Args:
        content: 原始提醒内容
        level: 提醒级别 (1-7)
        style: 通知风格 (warm/casual/professional)
        category: 任务分类 (可选，自动判断)

    Returns:
        温和的通知内容
    """
    if category is None:
        category = classify_category(content)

    urgency = get_urgency_level(level)

    # 获取对应风格的模板
    templates = STYLE_TEMPLATES.get(style, WARM_TEMPLATES)
    category_templates = templates.get(category, templates["general"])
    urgency_templates = category_templates.get(urgency, category_templates["medium"])

    # 随机选择一个模板
    template = random.choice(urgency_templates)

    # 填充内容
    message = template.format(content=content)

    return message


def should_notify_now(level: int) -> bool:
    """判断当前是否应该发送通知（深夜不打扰）"""
    hour = datetime.now().hour

    # 深夜 22:00 - 早上 08:00
    if 22 <= hour or hour < 8:
        # 只有强制提醒（级别 7）才在深夜通知
        return level >= 7

    return True
