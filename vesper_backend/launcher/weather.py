# launcher/weather.py — 天气通知轮询
"""launcher 天气通知——后台轮询天气通知文件并推送系统通知"""
import os
import json as _json
import time as _time
import logging
from . import _shared as _s

logger = logging.getLogger(__name__)


def _poll_weather_notifications():
    """后台轮询天气通知文件"""
    from .window import _show_toast
    last_check = ""
    while True:
        _time.sleep(120)
        try:
            if os.path.exists(_s.WEATHER_NOTIFICATION_FILE):
                with open(_s.WEATHER_NOTIFICATION_FILE, "r", encoding="utf-8") as f:
                    data = _json.load(f)
                created = data.get("created_at", "")
                if created != last_check:
                    last_check = created
                    weather = data.get("weather", {})
                    city = weather.get("city", "")
                    temp = weather.get("temp", "?")
                    desc = weather.get("weather", "未知")
                    suggestion = weather.get("suggestion", "")
                    push_hour = weather.get("push_hour", 0)

                    from core.db import get_config
                    _name = get_config("ai_name", "夕语")
                    if push_hour == 7:
                        title = f"{_name} · 早安天气"
                    elif push_hour == 12:
                        title = f"{_name} · 午间天气"
                    elif push_hour == 19:
                        title = f"{_name} · 晚间天气"
                    else:
                        title = f"{_name} · 天气"

                    body = f"{city} {desc} {temp}°C"
                    if suggestion:
                        body += f"\n{suggestion}"
                    forecasts = weather.get("forecast", [])
                    for fc in forecasts:
                        label = fc.get("label", "")
                        w = fc.get("weather", "")
                        high = fc.get("high", "?")
                        low = fc.get("low", "?")
                        body += f"\n{label}: {w} {low}~{high}°C"

                    _show_toast(title, body)
                    try:
                        os.remove(_s.WEATHER_NOTIFICATION_FILE)
                    except OSError:
                        pass
        except Exception as e:
            logger.warning(f"[launcher] 天气通知轮询异常: {e}")