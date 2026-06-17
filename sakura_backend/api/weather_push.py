# api/weather_push.py — 天气定时推送（从 api/chat.py 提取）
import asyncio
import json
import os
from datetime import datetime, timedelta
from core.db import get_config, add_chat_message
import logging
logger = logging.getLogger(__name__)

WEATHER_NOTIFICATION_FILE = "data/weather_notification.json"


async def weather_scheduler(active_websockets: dict, active_websockets_lock: asyncio.Lock):
    """全局天气定时推送（7:00, 12:00, 19:00）"""
    pushed_slots = set()
    while True:
        now = datetime.now()
        targets = [7, 12, 19]
        next_h = None
        for h in targets:
            t = now.replace(hour=h, minute=0, second=0, microsecond=0)
            if t > now:
                next_h = h
                delay = (t - now).total_seconds()
                break
        if next_h is None:
            delay = (now.replace(hour=7, minute=0, second=0, microsecond=0) + timedelta(days=1) - now).total_seconds()
        await asyncio.sleep(delay + 1)
        if not get_config("use_weather_care", True):
            continue
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        hour = now.hour
        if hour in (7, 12, 19) and (today, hour) not in pushed_slots:
            pushed_slots.add((today, hour))
            try:
                await _push_weather(hour, active_websockets, active_websockets_lock)
            except Exception as e:
                logger.warning(f"[天气调度] 推送异常: {e}")


async def _push_weather(push_hour: int, active_websockets: dict, active_websockets_lock: asyncio.Lock):
    from core.weather import get_weather_for_city, build_weather_card_data
    city = get_config("precise_city") or get_config("manual_city") or "北京"
    for attempt in range(2):
        weather = await asyncio.to_thread(get_weather_for_city, city)
        card_data = build_weather_card_data(weather, push_hour)
        if "error" not in card_data:
            break
        logger.warning(f"[天气调度] 第{attempt+1}次获取失败: {card_data['error']}")
        if attempt == 0:
            await asyncio.sleep(60)  # 等 60 秒重试一次
    else:
        logger.warning(f"[天气调度] 2次尝试均失败，本时段跳过")
        return
    if active_websockets:
        await _broadcast_weather(card_data, active_websockets, active_websockets_lock)
    else:
        _write_weather_notification(card_data)


async def _broadcast_weather(card_data: dict, active_websockets: dict, active_websockets_lock: asyncio.Lock):
    message = json.dumps({"type": "weather", "data": card_data}, ensure_ascii=False)
    disconnected = []
    async with active_websockets_lock:
        for conn_id, ws in list(active_websockets.items()):
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(conn_id)
        for cid in disconnected:
            active_websockets.pop(cid, None)
    # 同时存入聊天记录
    add_chat_message("assistant", f"__WEATHER_CARD__{json.dumps(card_data, ensure_ascii=False)}")
    logger.info(f"[天气调度] 已广播天气到 {len(active_websockets)} 个连接")


def _write_weather_notification(card_data: dict):
    try:
        os.makedirs("data", exist_ok=True)
        with open(WEATHER_NOTIFICATION_FILE, "w", encoding="utf-8") as f:
            json.dump({"weather": card_data, "created_at": datetime.now().isoformat()}, f, ensure_ascii=False)
        logger.info(f"[天气调度] 已写入天气通知文件")
    except Exception as e:
        logger.warning(f"[天气调度] 写入文件失败: {e}")