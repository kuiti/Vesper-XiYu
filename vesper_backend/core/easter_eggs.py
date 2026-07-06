# core/easter_eggs.py — 彩蛋系统
"""关键词触发特殊回复 + 节日彩蛋"""
import random
import datetime

EASTER_EGGS = {
    "我饿了": ["饿了就去吃点好的~", "想吃啥？我给你推荐", "别饿着自己，去吃点东西吧"],
    "好无聊": ["那我陪你聊聊天吧", "要不要玩个小游戏？", "我给你讲个冷知识？"],
    "晚安": ["晚安，做个好梦~", "晚安！明天见", "晚安，早点休息哦"],
    "早上好": ["早安！今天也要加油~", "早上好呀~", "早！新的一天开始了"],
    "我爱你": ["…哼，谁要你说这个", "我也…才不告诉你", "你、你说什么呢！"],
    "你好厉害": ["还、还行吧", "那是当然", "没有啦…"],
}

HOLIDAY_EGGS = {
    "01-01": "新年快乐！新的一年也要开心哦🎉",
    "02-14": "情人节快乐~有情人终成眷属💕",
    "03-08": "女神节快乐！",
    "05-01": "劳动节快乐~好好休息",
    "05-20": "今天是个特别的日子呢…520💕",
    "06-01": "儿童节快乐！谁还不是个宝宝呢",
    "09-10": "教师节快乐！",
    "10-01": "国庆节快乐！",
    "12-24": "平安夜快乐🎄",
    "12-25": "圣诞快乐🎄",
    "12-31": "跨年快乐！新的一年见~",
}


def check_easter_egg(text: str) -> str | None:
    """检查是否触发彩蛋"""
    if not text:
        return None
    for keyword, replies in EASTER_EGGS.items():
        if keyword in text:
            if random.random() < 0.3:
                return random.choice(replies)
    return None


def check_holiday() -> str | None:
    """检查是否节日"""
    today = datetime.datetime.now().strftime("%m-%d")
    return HOLIDAY_EGGS.get(today)
