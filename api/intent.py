# version: 3.9.0
import requests
import re
from datetime import datetime
from core.db import get_config

def get_location_by_ip() -> dict:
    """获取位置：高德IP优先，失败用ipapi.co备用"""
    api_key = get_config("amap_key", "")
    if api_key:
        try:
            resp = requests.get(f"https://restapi.amap.com/v3/ip?key={api_key}", timeout=5)
            data = resp.json()
            if data.get("status") == "1":
                province = data.get("province", "")
                city = data.get("city", "")
                if isinstance(province, list): province = ""
                if isinstance(city, list): city = ""
                if city:
                    return {"province": province, "city": city, "adcode": data.get("adcode", "")}
        except Exception as e:
            print(f"[意图-定位] 高德异常: {e}")
    # 备用: ip-api.com
    try:
        resp = requests.get("https://ip-api.com/json/?lang=zh-CN", timeout=5)
        data = resp.json()
        if data.get("status") == "success":
            return {"province": data.get("regionName", ""), "city": data.get("city", ""), "adcode": ""}
    except Exception as e:
        print(f"[意图] 异常: {e}")
    return {}

def get_city_by_ip():
    loc = get_location_by_ip()
    return loc.get("city") or None

def get_weather_forecast(city: str) -> dict:
    api_key = get_config("amap_key", "")
    if not api_key:
        return {"error": "未配置高德地图 API Key"}
    url = f"https://restapi.amap.com/v3/weather/weatherInfo?key={api_key}&city={city}&extensions=all"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get("status") == "1":
            city_forecasts = data.get("forecasts", [])
            if city_forecasts and city_forecasts[0].get("casts"):
                return {"city": city, "casts": city_forecasts[0]["casts"]}
        return {"error": data.get("info", "获取天气失败")}
    except Exception as e:
        return {"error": str(e)}

def get_current_weather(city: str) -> dict:
    """获取实时天气（含湿度）"""
    api_key = get_config("amap_key", "")
    if not api_key:
        return {}
    try:
        url = f"https://restapi.amap.com/v3/weather/weatherInfo?key={api_key}&city={city}&extensions=base"
        resp = requests.get(url, timeout=10).json()
        if resp.get("status") == "1" and resp.get("lives"):
            return resp["lives"][0]
    except Exception as e:
        print(f"[意图] 异常: {e}")
    return {}

# ─── 天气代码映射 (WMO) ───
WMO_WEATHER = {0:"晴天",1:"少云",2:"多云",3:"阴天",45:"雾",48:"霜雾",51:"小毛毛雨",53:"毛毛雨",55:"浓毛毛雨",61:"小雨",63:"中雨",65:"大雨",66:"小冻雨",67:"冻雨",71:"小雪",73:"中雪",75:"大雪",77:"雪粒",80:"小阵雨",81:"阵雨",82:"强阵雨",85:"小阵雪",86:"阵雪",95:"雷暴",96:"小冰雹雷暴",99:"大冰雹雷暴"}

def get_city_coords(city: str) -> dict:
    """通过城市名获取经纬度（Open-Meteo 地理编码）"""
    try:
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=zh"
        resp = requests.get(url, timeout=8)
        data = resp.json()
        if data.get("results"):
            r = data["results"][0]
            return {"lat": r["latitude"], "lng": r["longitude"], "name": r.get("name", city), "country": r.get("country", "")}
    except Exception as e:
        print(f"[意图] 异常: {e}")
    return {}

def get_openmeteo_weather(lat: float, lng: float) -> dict:
    """获取 Open-Meteo 全面天气数据（免费，无需 API Key）"""
    try:
        fields = "temperature_2m,relative_humidity_2m,apparent_temperature,wind_speed_10m,wind_direction_10m,weather_code,surface_pressure,cloud_cover,precipitation,visibility,dew_point_2m"
        daily = "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,wind_direction_10m_dominant"
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&current={fields}&daily={daily}&timezone=auto&forecast_days=3"
        resp = requests.get(url, timeout=10)
        data = resp.json()
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
                    "weather_code": daily_data.get("weather_code", [None])[i] if i < len(daily_data.get("weather_code", [])) else None,
                    "weather": WMO_WEATHER.get(daily_data.get("weather_code", [None])[i], "未知") if i < len(daily_data.get("weather_code", [])) else None,
                    "temp_max": daily_data.get("temperature_2m_max", [None])[i] if i < len(daily_data.get("temperature_2m_max", [])) else None,
                    "temp_min": daily_data.get("temperature_2m_min", [None])[i] if i < len(daily_data.get("temperature_2m_min", [])) else None,
                    "precipitation_sum": daily_data.get("precipitation_sum", [None])[i] if i < len(daily_data.get("precipitation_sum", [])) else None,
                    "wind_speed_max": daily_data.get("wind_speed_10m_max", [None])[i] if i < len(daily_data.get("wind_speed_10m_max", [])) else None,
                    "wind_direction": daily_data.get("wind_direction_10m_dominant", [None])[i] if i < len(daily_data.get("wind_direction_10m_dominant", [])) else None,
                }
                for i in range(len(daily_data.get("time", [])))
            ] if daily_data.get("time") else []
        }
    except Exception as e:
        return {"error": str(e)}

def wind_direction_name(deg: float) -> str:
    if deg is None: return ""
    dirs = ["北","东北","东","东南","南","西南","西","西北"]
    return dirs[int(deg / 45 + 0.5) % 8]

def build_weather_text(casts: list) -> str:
    hour = datetime.now().hour
    today = casts[0] if len(casts) > 0 else None
    tomorrow = casts[1] if len(casts) > 1 else None
    after_tomorrow = casts[2] if len(casts) > 2 else None
    if not today:
        return "暂无天气数据"

    if 5 <= hour < 12:
        text = f"今天（{today['date']}）白天{today['dayweather']}，温度{today['daytemp']}°C，夜间{today['nightweather']}，温度{today['nighttemp']}°C，{today['daywind']}风{today['daypower']}级。"
        if tomorrow:
            text += f"明天（{tomorrow['date']}）白天{tomorrow['dayweather']}，温度{tomorrow['daytemp']}°C，夜间{tomorrow['nightweather']}，温度{tomorrow['nighttemp']}°C。"
    elif 12 <= hour < 18:
        text = f"今天下午到夜间{today['nightweather']}，温度{today['nighttemp']}°C。"
        if tomorrow:
            text += f"明天（{tomorrow['date']}）白天{tomorrow['dayweather']}，温度{tomorrow['daytemp']}°C，夜间{tomorrow['nightweather']}，温度{tomorrow['nighttemp']}°C。"
    else:
        text = f"今晚{today['nightweather']}，温度{today['nighttemp']}°C。"
        if tomorrow:
            text += f"明天（{tomorrow['date']}）白天{tomorrow['dayweather']}，温度{tomorrow['daytemp']}°C，夜间{tomorrow['nightweather']}，温度{tomorrow['nighttemp']}°C。"
        if after_tomorrow:
            text += f"后天（{after_tomorrow['date']}）{after_tomorrow['dayweather']}，{after_tomorrow['daytemp']}°C~{after_tomorrow['nighttemp']}°C。"
    return text

def web_search(query: str) -> str:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
            if results:
                return "\n\n".join([f"{r['title']}：{r['body'][:150]}" for r in results])
            return "未找到相关信息"
    except Exception as e:
        return f"搜索出错：{str(e)}"

# ─── 意图关键词 ─────────────────────────────────

WEATHER_PATTERNS = [
    r"天气", r"气温", r"几度", r"冷不冷", r"热不热", r"冷吗", r"热吗",
    r"下雨", r"下雪", r"刮风", r"阴天", r"晴天", r"多云", r"雾霾",
    r"温度", r"湿度", r"风速", r"紫外线",
    r"穿什么", r"带伞", r"带雨", r"会不会下",
    r"外面.*冷", r"外面.*热", r"外面.*风", r"外面.*晒",
    r"今天.*天", r"明天.*天", r"后天.*天",
    r"预报", r"降温", r"升温", r"变天",
    # 口语化表达
    r"好热", r"好冷", r"真热", r"真冷", r"热死", r"冷死",
    r"闷热", r"凉快", r"暖和", r"冻死",
    r"会不会下雨", r"要不要带伞", r"带不带伞",
    r"今天穿什么", r"穿多少", r"穿厚点", r"穿薄点",
    r"适合出门", r"能出门", r"适合.*玩",
    r"换季", r"入秋", r"入冬", r"入夏", r"入春",
    r"秋裤", r"短袖", r"外套", r"羽绒服",
    # 追问（承接上次天气话题）
    r"那明天", r"那后天", r"明天会", r"后天会",
    r"下周.*天气", r"周末.*天气", r"这周.*天气",
]

LOCATION_PATTERNS = [
    r"在哪", r"哪里", r"什么地方", r"什么城市", r"哪个城市",
    r"位置", r"定位", r"我在哪", r"我这是",
    r"告诉我.*位置", r"我现在.*位置",
    r"我在.*地方", r"我在.*城市",
    r"这里.*哪里", r"这是.*城市",
    # 口语化表达
    r"这是哪", r"哪个省", r"哪个区", r"什么省", r"什么区",
    r"我目前在", r"我现在在", r"当前.*位置",
    r"能.*定位", r"帮我.*定位",
    r"告诉我.*在哪", r"查.*位置",
]

SEARCH_PATTERNS = [
    r"搜索", r"查一下", r"帮我查", r"帮我搜", r"百度",
    r"搜索.*一下", r"帮我.*查", r"帮我.*搜",
    r"查一查", r"搜一搜", r"上网查", r"网上查",
    r"查查", r"找一找", r"搜一下",
    r"帮.*百度", r"百度一下",
    r"用网.*查", r"联网.*查", r"联网.*搜",
]

NEWS_PATTERNS = [
    r"最近.*新闻", r"今天.*新闻", r"最新.*消息", r"最新.*新闻",
    r"有什么.*新闻", r"有什么.*大事", r"发生.*什么",
    r"最近.*发生", r"热点", r"头条",
    r"最近.*怎么样", r"最近.*如何",
    r"现在.*什么.*最.*[新火热]", r"今天.*大事",
    r"告诉我.*最近", r"最近.*知道",
    r"现实.*新闻", r"外面.*发生",
    r"有没有.*新闻", r"新闻.*头条", r"热搜",
    r"世界上.*发生", r"国际上.*发生",
]

KNOWLEDGE_PATTERNS = [
    r"什么是", r"是谁", r"怎么样", r"如何", r"为什么",
    r"介绍一下", r"介绍一下", r"告诉我.*关于",
    r"我不.*知道.*什么", r"我不.*了解",
    r"能.*告诉.*我.*关于", r"知道.*关于",
    r"科普", r"定义", r"解释.*一下",
    r"是什么意思", r"啥意思", r"什么意思",
]

def match_any(msg: str, patterns: list) -> bool:
    for p in patterns:
        if re.search(p, msg):
            return True
    return False

def extract_search_query(msg: str, prefixes: list) -> str:
    """从消息中提取搜索关键词"""
    for prefix in prefixes:
        m = re.search(prefix + r"\s*(.+)", msg)
        if m:
            return m.group(1).strip()
    # 没有前缀则用整条消息
    return msg.strip()

def detect_intent(user_message: str) -> tuple:
    # 天气
    if match_any(user_message, WEATHER_PATTERNS):
        city = get_config("precise_city") or get_city_by_ip() or get_config("default_city") or "北京"
        # 1. 尝试 Open-Meteo 全面数据（免费，无需 key）
        coords = get_city_coords(city)
        if coords:
            om = get_openmeteo_weather(coords["lat"], coords["lng"])
            if "error" not in om:
                parts = [f"{city}天气："]
                if om.get("weather"):
                    parts.append(om['weather'])
                if om.get("temp") is not None:
                    parts.append(f"{om['temp']}°C")
                # 最多追加 3 个额外字段，按优先级
                extras = []
                if om.get("precipitation", 0) > 0:
                    extras.append(f"降水{om['precipitation']}mm")
                if om.get("wind_speed") is not None:
                    extras.append(f"{wind_direction_name(om.get('wind_direction'))}风{om['wind_speed']}km/h")
                if om.get("feels_like") is not None and abs(om["feels_like"] - om.get("temp", 0)) > 3:
                    extras.append(f"体感{om['feels_like']}°C")
                if om.get("humidity") is not None:
                    extras.append(f"湿度{om['humidity']}%")
                parts.extend(extras[:3])
                # 预报只给明天一条
                if om.get("daily") and len(om["daily"]) > 1:
                    d = om["daily"][1]
                    dname = d["date"][-5:] if d.get("date") else "明天"
                    parts.append(f"{dname} {d.get('weather','')} {d.get('temp_min','')}~{d.get('temp_max','')}°C")
                weather_text = "，".join(parts)
                return ("weather", {"city": coords.get("name", city), "text": weather_text})
        # 2. 回退 Amap
        forecast = get_weather_forecast(city)
        live = get_current_weather(city)
        humidity_str = f"，湿度{live['humidity']}%" if live.get("humidity") else ""
        if "error" not in forecast:
            weather_text = build_weather_text(forecast["casts"]) + humidity_str
            return ("weather", {"city": city, "text": weather_text})
        if live:
            l = live
            return ("weather", {"city": city, "text": f"今天{l.get('weather','未知')}，温度{l.get('temperature','?')}°C，{l.get('winddirection','')}风{l.get('windpower','?')}级，湿度{l.get('humidity','?')}%"})

    # 位置
    if match_any(user_message, LOCATION_PATTERNS):
        precise_city = get_config("precise_city", "")
        if precise_city:
            ip_loc = get_location_by_ip()
            return ("location", {"province": ip_loc.get("province", ""), "city": precise_city})
        ip_loc = get_location_by_ip()
        if ip_loc.get("city"):
            return ("location", ip_loc)

    # 联网搜索
    if get_config("enable_web_search", True):
        # 新闻/热点
        if match_any(user_message, NEWS_PATTERNS):
            query = extract_search_query(user_message, ["最近新闻", "新闻", "最新消息", "热点", "头条", "告诉我"])
            result = web_search(query + " 新闻")
            if "未找到" not in result and "出错" not in result:
                return ("search", result)

        # 知识问答
        elif match_any(user_message, KNOWLEDGE_PATTERNS):
            query = extract_search_query(user_message, ["什么是", "是谁", "介绍一下", "告诉我关于", "为什么", "如何", "怎么样"])
            result = web_search(query)
            if "未找到" not in result and "出错" not in result:
                return ("search", result)

        # 明确搜索
        elif match_any(user_message, SEARCH_PATTERNS):
            query = extract_search_query(user_message, ["搜索", "查一下", "帮我查", "帮我搜", "百度", "上网查", "网上查", "查一查", "搜一搜"])
            if query and query != user_message:
                result = web_search(query)
                if "未找到" not in result and "出错" not in result:
                    return ("search", result)

    return (None, None)
