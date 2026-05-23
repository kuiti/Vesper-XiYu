# core/weather.py — 天气服务模块
"""可复用的天气获取与格式化，供 intent.py 和天气关怀调度器共用"""

import requests
from datetime import datetime
from core.db import get_config

# WMO 天气代码映射
WMO_WEATHER = {
    0: "晴天", 1: "少云", 2: "多云", 3: "阴天",
    45: "雾", 48: "霜雾",
    51: "小毛毛雨", 53: "毛毛雨", 55: "浓毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "小冻雨", 67: "冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒",
    80: "小阵雨", 81: "阵雨", 82: "强阵雨",
    85: "小阵雪", 86: "阵雪",
    95: "雷暴", 96: "小冰雹雷暴", 99: "大冰雹雷暴"
}


def get_city_coords(city: str) -> dict:
    """通过城市名获取经纬度（Open-Meteo 地理编码）"""
    try:
        resp = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "zh"},
            timeout=8
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("results"):
            r = data["results"][0]
            return {"lat": r["latitude"], "lng": r["longitude"],
                    "name": r.get("name", city), "country": r.get("country", "")}
    except Exception as e:
        print(f"[天气] 坐标获取异常: {e}")
    return {}


def get_openmeteo_weather(lat: float, lng: float) -> dict:
    """获取 Open-Meteo 全面天气数据"""
    try:
        fields = ("temperature_2m,relative_humidity_2m,apparent_temperature,"
                  "wind_speed_10m,wind_direction_10m,weather_code,"
                  "surface_pressure,cloud_cover,precipitation,visibility,dew_point_2m")
        daily = ("weather_code,temperature_2m_max,temperature_2m_min,"
                 "precipitation_sum,wind_speed_10m_max,wind_direction_10m_dominant")
        url = (f"https://api.open-meteo.com/v1/forecast"
               f"?latitude={lat}&longitude={lng}"
               f"&current={fields}&daily={daily}"
               f"&timezone=auto&forecast_days=3")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            print(f"[天气] API 错误: {data.get('reason', '未知')}")
            return {}
        current = data.get("current", {})
        daily_data = data.get("daily", {})
        return {
            "temp": current.get("temperature_2m"),
            "humidity": current.get("relative_humidity_2m"),
            "feels_like": current.get("apparent_temperature"),
            "wind_speed": current.get("wind_speed_10m"),
            "wind_direction": current.get("wind_direction_10m"),
            "weather_code": current.get("weather_code"),
            "weather": WMO_WEATHER.get(current.get("weather_code", -1), "未知"),
            "pressure": current.get("surface_pressure"),
            "cloud_cover": current.get("cloud_cover"),
            "precipitation": current.get("precipitation"),
            "visibility": current.get("visibility"),
            "dew_point": current.get("dew_point_2m"),
            "daily": [
                {
                    "date": daily_data.get("time", [None])[i],
                    "weather": WMO_WEATHER.get(
                        daily_data.get("weather_code", [None])[i], "未知"
                    ) if i < len(daily_data.get("weather_code", [])) else None,
                    "temp_max": daily_data.get("temperature_2m_max", [None])[i]
                        if i < len(daily_data.get("temperature_2m_max", [])) else None,
                    "temp_min": daily_data.get("temperature_2m_min", [None])[i]
                        if i < len(daily_data.get("temperature_2m_min", [])) else None,
                    "precipitation_sum": daily_data.get("precipitation_sum", [None])[i]
                        if i < len(daily_data.get("precipitation_sum", [])) else None,
                }
                for i in range(len(daily_data.get("time", [])))
            ] if daily_data.get("time") else []
        }
    except Exception as e:
        return {"error": str(e)}


def wind_direction_name(deg: float) -> str:
    if deg is None:
        return ""
    dirs = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
    return dirs[int(deg / 45 + 0.5) % 8]


def get_weather_for_city(city: str = None) -> dict:
    """统一天气获取入口：城市 -> 坐标 -> 天气数据"""
    if not city:
        city = get_config("precise_city") or "北京"
    coords = get_city_coords(city)
    if not coords:
        return {"error": f"无法获取 {city} 的坐标"}
    weather = get_openmeteo_weather(coords["lat"], coords["lng"])
    if "error" in weather:
        return weather
    weather["city"] = coords.get("name", city)
    return weather


def get_weather_suggestion(weather: dict, hour: int) -> str:
    """根据天气数据生成穿衣/出行建议"""
    temp = weather.get("temp")
    if temp is None:
        return ""
    suggestions = []
    daily = weather.get("daily", [])
    today_rain = daily[0].get("precipitation_sum", 0) if daily else 0

    if hour < 12:
        if temp < 5:
            suggestions.append("今天很冷，出门记得穿厚外套")
        elif temp < 15:
            suggestions.append("早上有点凉，带件外套")
        elif temp > 35:
            suggestions.append("今天很热，注意防暑")
        if (today_rain or 0) > 0:
            suggestions.append("今天有雨，记得带伞")
    elif hour < 19:
        if temp > 33:
            suggestions.append("下午很热，注意补水")
    else:
        if daily and len(daily) > 1:
            tmr = daily[1]
            if (tmr.get("precipitation_sum", 0) or 0) > 0:
                suggestions.append("明天有雨，出门提前准备")
            if tmr.get("temp_min") is not None and tmr["temp_min"] < 10:
                suggestions.append("明天降温，注意添衣")
    return "。".join(suggestions) + "。" if suggestions else ""


def build_weather_card_data(weather: dict, push_hour: int) -> dict:
    """构建天气卡片数据结构，供 WebSocket 推送到前端"""
    if "error" in weather:
        return {"error": weather["error"]}

    result = {
        "city": weather.get("city", ""),
        "temp": weather.get("temp"),
        "feels_like": weather.get("feels_like"),
        "humidity": weather.get("humidity"),
        "weather": weather.get("weather", "未知"),
        "wind_speed": weather.get("wind_speed"),
        "wind_direction": wind_direction_name(weather.get("wind_direction")),
        "precipitation": weather.get("precipitation", 0),
        "push_hour": push_hour,
        "suggestion": get_weather_suggestion(weather, push_hour),
        "forecast": []
    }

    daily = weather.get("daily", [])
    if push_hour == 7 and daily:
        d = daily[0]
        result["forecast"] = [{
            "label": "今天",
            "weather": d.get("weather"),
            "high": d.get("temp_max"),
            "low": d.get("temp_min"),
            "rain": d.get("precipitation_sum", 0)
        }]
    elif push_hour == 19 and daily and len(daily) > 1:
        d = daily[1]
        result["forecast"] = [{
            "label": "明天",
            "weather": d.get("weather"),
            "high": d.get("temp_max"),
            "low": d.get("temp_min"),
            "rain": d.get("precipitation_sum", 0)
        }]
    return result
