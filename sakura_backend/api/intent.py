# version: 6.0.0
import hashlib
import requests
import re
import threading as _threading
from datetime import datetime
from core.db import get_config

# ─── LLM 意图分类缓存 ───
_llm_intent_cache = {}
_llm_intent_lock = _threading.Lock()

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

# 天气相关函数统一从 core.weather 导入，不再重复定义
from core.weather import WMO_WEATHER, get_city_coords, get_openmeteo_weather, wind_direction_name


def build_weather_text(casts: list) -> str:
    hour = datetime.now().hour
    today = casts[0] if len(casts) > 0 else None
    tomorrow = casts[1] if len(casts) > 1 else None
    after_tomorrow = casts[2] if len(casts) > 2 else None
    if not today:
        return "暂无天气数据"

    if 5 <= hour < 12:
        text = f"今天（{today['date']}）白天{today['dayweather']}，温度{today['daytemp']}度，夜间{today['nightweather']}，温度{today['nighttemp']}度，{today['daywind']}风{today['daypower']}级。"
        if tomorrow:
            text += f"明天（{tomorrow['date']}）白天{tomorrow['dayweather']}，温度{tomorrow['daytemp']}度，夜间{tomorrow['nightweather']}，温度{tomorrow['nighttemp']}度。"
    elif 12 <= hour < 18:
        text = f"今天下午到夜间{today['nightweather']}，温度{today['nighttemp']}度。"
        if tomorrow:
            text += f"明天（{tomorrow['date']}）白天{tomorrow['dayweather']}，温度{tomorrow['daytemp']}度，夜间{tomorrow['nightweather']}，温度{tomorrow['nighttemp']}度。"
    else:
        text = f"今晚{today['nightweather']}，温度{today['nighttemp']}度。"
        if tomorrow:
            text += f"明天（{tomorrow['date']}）白天{tomorrow['dayweather']}，温度{tomorrow['daytemp']}度，夜间{tomorrow['nightweather']}，温度{tomorrow['nighttemp']}度。"
        if after_tomorrow:
            text += f"后天（{after_tomorrow['date']}）{after_tomorrow['dayweather']}，{after_tomorrow['daytemp']}度~{after_tomorrow['nighttemp']}度。"
    return text

def web_search(query: str) -> str:
    """联网搜索。DDG（重试1次）→ Bing。容错优先。"""
    # 方案1: DuckDuckGo
    import time as _time
    for attempt in range(2):
        try:
            from duckduckgo_search import DDGS
            with DDGS(timeout=8) as ddgs:
                results = list(ddgs.text(query, max_results=3))
                if results:
                    return "\n\n".join([f"{r['title']}：{r['body'][:150]}" for r in results])
                break  # DDG 返回空，不重试
        except Exception as e:
            if attempt == 0:
                _time.sleep(2)
            else:
                print(f"[搜索] DDG 失败: {e}")

    # 方案2: Bing 备用
    try:
        resp = requests.get(
            f"https://www.bing.com/search?q={requests.utils.quote(query)}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=8
        )
        if resp.status_code == 200:
            from re import findall
            from html.parser import HTMLParser
            class _Stripper(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.parts = []
                def handle_data(self, data):
                    self.parts.append(data)
                def get_text(self):
                    return ''.join(self.parts)
            snippets = findall(r'<p[^>]*class=["\']?[^"\'>]*\bb_caption\b[^>]*>(.*?)</p>', resp.text, flags=re.DOTALL)
            if not snippets:
                snippets = findall(r'<p[^>]*>(.*?)</p>', resp.text, flags=re.DOTALL)
            clean = []
            for s in snippets[:3]:
                stripper = _Stripper()
                stripper.feed(s)
                s = stripper.get_text().strip()
                if len(s) > 20:
                    clean.append(s[:200])
            if clean:
                return "\n\n".join(clean)
    except Exception as e:
        print(f"[搜索] Bing 备用失败: {e}")

    return ""

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
    r"最近.*新闻.*如何",
    r"现在.*什么.*最.*[新火热]", r"今天.*大事",
    r"告诉我.*最近", r"最近.*知道",
    r"现实.*新闻", r"外面.*发生",
    r"有没有.*新闻", r"新闻.*头条", r"热搜",
    r"世界上.*发生", r"国际上.*发生",
]

KNOWLEDGE_PATTERNS = [
    r"什么是", r"介绍一下", r"告诉我.*关于",
    r"我不.*知道.*什么", r"我不.*了解",
    r"能.*告诉.*我.*关于", r"知道.*关于",
    r"科普", r"定义", r"解释.*一下",
    r"是什么意思", r"啥意思", r"什么意思",
]

# 泛化知识模式（需排除情感/关系类问题）
FUZZY_KNOWLEDGE_PATTERNS = [
    r"是谁", r"怎么用", r"怎么做", r"怎么实现",
    r"为什么.*会", r"为什么.*是", r"为什么.*不",
    r"如何.*做", r"如何.*用", r"如何.*实现",
    r"怎么样.*的", r"怎么样.*才",
]

def _is_emotional_question(msg: str) -> bool:
    """检测是否为情感/关系类问题（不应触发搜索）"""
    emotional_markers = ["不理我", "你生气", "你难过", "你不开心", "你喜欢我", "你是不是", "你怎么了", "你在吗", "你爱我", "你想我", "你怎么样", "最近怎么样", "最近咋样", "最近好吗", "最近如何", "你好吗", "你还好吗", "你还好吧", "你咋样", "在干嘛", "在做什么", "最近忙", "想你了", "我应该如何", "我该怎么", "我怎么跟她", "我怎么跟他", "要不要分手", "该不该", "表白", "暗恋", "喜欢的人", "讨厌"]
    return any(m in msg for m in emotional_markers)

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

def llm_classify_intent(user_message: str) -> dict:
    """LLM 意图分类（正则未命中时的兜底路径）
    返回 {"intent": str, "confidence": float, "query": str|None}
    """
    key = hashlib.sha256(user_message.strip().encode()).hexdigest()
    with _llm_intent_lock:
        if key in _llm_intent_cache:
            return _llm_intent_cache[key].copy()

    api_key = get_config("api_key", "")
    if not api_key:
        return {"intent": "chat", "confidence": 0, "query": None}

    prompt = f"""分类用户消息意图。只输出JSON，不要解释。
{{"intent":"类型","confidence":0到1的数值,"query":"提取的搜索关键词或null"}}

意图类型：
- weather: 天气相关（"周末去爬山会下雨吗""穿什么出门"）
- search: 需要联网查（"推荐个电影""最近有什么新闻""A和B哪个好"）
- knowledge: 知识问答（"量子力学是什么""为什么天空是蓝的"）
- location: 位置/定位（"我现在在哪""这是哪个城市"）
- how_to: 教程/方法（"怎么做蛋炒饭""怎么学编程"）
- emotional: 情感倾诉（"我今天心情不好""好累啊"）
- roleplay: 角色扮演（"假装你是我女朋友""你来当老师"）
- chat: 普通闲聊（"你好""在干嘛""晚安"）

规则：
- 只要涉及查资料、找推荐、比价、新闻 → search
- 涉及天气、温度、穿衣、带伞 → weather
- 情感倾诉、撒娇、抱怨生活 → emotional
- confidence: 正则能覆盖的明确意图给0.9+，模糊的给0.6-0.8
- query: search/knowledge/weather 类型提取核心关键词，其他类型为null

用户消息：{user_message[:200]}"""

    from core.llm_client import call_llm
    result = call_llm(prompt=prompt, temperature=0, max_tokens=80, timeout=8, json_mode=True)
    if result and isinstance(result, dict):
        validated = {
            "intent": result.get("intent", "chat"),
            "confidence": min(1.0, max(0.0, float(result.get("confidence", 0)))),
            "query": result.get("query") if isinstance(result.get("query"), str) else None
        }
        with _llm_intent_lock:
            _llm_intent_cache[key] = validated
            if len(_llm_intent_cache) > 300:
                _llm_intent_cache.pop(next(iter(_llm_intent_cache)))
        return validated
    return {"intent": "chat", "confidence": 0, "query": None}


def detect_intent(user_message: str) -> tuple:
    """混合意图路由：正则快速路径 → LLM 兜底"""
    # ── 第一层：正则快速路径（0ms，0 token）──
    result = _regex_detect(user_message)
    if result[0] is not None:
        return result

    # ── 第二层：LLM 分类兜底 ──
    llm_result = llm_classify_intent(user_message)
    intent = llm_result["intent"]
    confidence = llm_result["confidence"]
    query = llm_result["query"]

    if confidence < 0.6:
        return (None, None)

    # 天气 → 走现有天气逻辑
    if intent == "weather":
        return _handle_weather(user_message)
    # 搜索类 → 统一走搜索
    if intent in ("search", "knowledge", "how_to", "recommendation"):
        search_query = query or user_message
        result = web_search(search_query)
        if result:
            return ("search", result)
    # 位置
    if intent == "location":
        precise_city = get_config("precise_city", "")
        if precise_city:
            ip_loc = get_location_by_ip()
            return ("location", {"province": ip_loc.get("province", ""), "city": precise_city})
        ip_loc = get_location_by_ip()
        if ip_loc.get("city"):
            return ("location", ip_loc)

    # emotional / roleplay / chat → 不拦截，走正常聊天
    return (None, None)


def _regex_detect(user_message: str) -> tuple:
    """正则快速路径（原 detect_intent 的匹配逻辑）"""
    # ── 排除规则：这些情况不触发意图 ──
    # 情感类排除（"我心里好冷"不是天气）
    if _is_emotional_question(user_message):
        return (None, None)

    # 用户在说自己的事（"我查一下消息"不是搜索，"帮我查一下待办"不是搜索）
    _self_action_patterns = [
        r"我.*查一下.*消息", r"我.*查一下.*记录", r"我.*查一下.*聊天",
        r"帮我查一下.*待办", r"帮我查一下.*日程", r"帮我查一下.*提醒",
        r"你查一下.*消息", r"你查一下.*记录", r"你查一下.*聊天",
        r"查一下.*消息", r"查一下.*记录", r"查一下.*聊天",
    ]
    if any(re.search(p, user_message) for p in _self_action_patterns):
        return (None, None)

    # 天气
    if match_any(user_message, WEATHER_PATTERNS):
        # 排除情感类天气表达
        _weather_exclude = [r"心里.*冷", r"心里.*热", r"心.*凉", r"心.*暖", r"世界.*冷", r"人心.*冷"]
        if any(re.search(p, user_message) for p in _weather_exclude):
            return (None, None)
        return _handle_weather(user_message)

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
        if match_any(user_message, NEWS_PATTERNS):
            query = extract_search_query(user_message, ["最近新闻", "新闻", "最新消息", "热点", "头条", "告诉我"])
            result = web_search(query + " 新闻")
            if result:
                return ("search", result)

        elif match_any(user_message, KNOWLEDGE_PATTERNS) or (match_any(user_message, FUZZY_KNOWLEDGE_PATTERNS) and not _is_emotional_question(user_message)):
            # 排除："你是什么意思""你是谁"等关于AI自身的问题
            _knowledge_exclude = [r"你.*是什么意思", r"你是谁", r"你.*什么意思", r"这话.*意思", r"你.*怎么了"]
            if any(re.search(p, user_message) for p in _knowledge_exclude):
                return (None, None)
            query = extract_search_query(user_message, ["什么是", "是谁", "介绍一下", "告诉我关于", "为什么", "如何", "怎么样"])
            result = web_search(query)
            if result:
                return ("search", result)

        elif match_any(user_message, SEARCH_PATTERNS):
            # 排除：用户在查自己的东西
            _search_exclude = [r"查一下.*消息", r"查一下.*记录", r"查一下.*待办", r"查一下.*日程", r"帮我查.*消息", r"帮我查.*待办"]
            if any(re.search(p, user_message) for p in _search_exclude):
                return (None, None)
            query = extract_search_query(user_message, ["搜索", "查一下", "帮我查", "帮我搜", "百度", "上网查", "网上查", "查一查", "搜一搜"])
            if query and query != user_message:
                result = web_search(query)
                if result:
                    return ("search", result)

    return (None, None)


def _handle_weather(user_message: str) -> tuple:
    """天气意图处理（从原 detect_intent 提取）"""
    city = get_config("precise_city") or get_config("manual_city") or get_city_by_ip() or get_config("default_city") or "北京"
    weather_text = None

    # 1. 高德优先（中文描述好，有湿度风力）
    forecast = get_weather_forecast(city)
    live = get_current_weather(city)
    if "error" not in forecast:
        weather_text = build_weather_text(forecast["casts"])
        if live.get("humidity") is not None:
            weather_text += f"，湿度{live['humidity']}%"
    elif live:
        l = live
        weather_text = f"{city}今天{l.get('weather','未知')}，温度{l.get('temperature','?')}度，{l.get('winddirection','')}风{l.get('windpower','?')}级，湿度{l.get('humidity','?')}%"

    # 2. wttr.in（免费无 Key）
    if not weather_text:
        try:
            from core.weather import get_wttr_weather
            w = get_wttr_weather(city)
            if "error" not in w and w.get("temp") is not None:
                parts = [f"{city}天气：{w['weather']}，{w['temp']}度"]
                extras = []
                if w.get("humidity") is not None:
                    extras.append(f"湿度{w['humidity']}%")
                if w.get("feels_like") is not None and abs(w["feels_like"] - (w.get("temp") or 0)) > 2:
                    extras.append(f"体感{w['feels_like']}度")
                if w.get("wind_speed") is not None:
                    extras.append(f"{w['wind_direction']}风{w['wind_speed']}km/h")
                if w.get("daily") and len(w["daily"]) > 1:
                    d = w["daily"][1]
                    extras.append(f"明天{d.get('weather','')} {d.get('temp_min','')}~{d.get('temp_max','')}度")
                if extras:
                    parts.append("，".join(extras))
                weather_text = "，".join(parts)
        except Exception:
            pass

    # 3. Open-Meteo 最后兜底
    if not weather_text:
        coords = get_city_coords(city)
        if coords:
            om = get_openmeteo_weather(coords["lat"], coords["lng"])
            if "error" not in om and om.get("temp") is not None:
                parts = [f"{coords.get('name', city)}天气：{om['weather']}，{om['temp']}度"]
                extras = []
                if om.get("humidity") is not None:
                    extras.append(f"湿度{om['humidity']}%")
                if om.get("feels_like") is not None and abs(om["feels_like"] - (om.get("temp") or 0)) > 2:
                    extras.append(f"体感{om['feels_like']}度")
                if om.get("wind_speed") is not None:
                    extras.append(f"{wind_direction_name(om.get('wind_direction'))}风{om['wind_speed']}km/h")
                if (om.get("precipitation") or 0) > 0:
                    extras.append(f"降水{om['precipitation']}mm")
                if om.get("daily") and len(om["daily"]) > 1:
                    d = om["daily"][1]
                    extras.append(f"明天{d.get('weather','')} {d.get('temp_min','')}~{d.get('temp_max','')}度")
                if extras:
                    parts.append("，".join(extras))
                weather_text = "，".join(parts)

    if weather_text:
        return ("weather", {"city": city, "text": weather_text})

    # 所有数据源都失败 → 让 LLM 自行发挥
    return ("weather", {"city": city, "text": ""})
