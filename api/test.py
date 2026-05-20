import requests
from fastapi import APIRouter
from core.db import get_config

router = APIRouter(prefix="/test", tags=["test"])

@router.get("/deepseek")
async def test_deepseek():
    api_key = get_config("api_key", "")
    if not api_key:
        return {"ok": False, "message": "未配置 API Key"}
    try:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": "回复OK即可"}],
            "max_tokens": 5,
            "temperature": 0
        }
        resp = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        return {"ok": True, "message": "DeepSeek API 正常"}
    except Exception as e:
        return {"ok": False, "message": str(e)}

@router.get("/weather")
async def test_weather():
    api_key = get_config("amap_key", "")
    if not api_key:
        return {"ok": False, "message": "未配置高德 API Key"}
    city = get_config("precise_city") or get_config("default_city") or "北京"
    try:
        from api.intent import get_weather_forecast, build_weather_text
        forecast = get_weather_forecast(city)
        if "error" not in forecast:
            text = build_weather_text(forecast["casts"])
            return {"ok": True, "city": city, "report": text}
        return {"ok": False, "message": "获取失败"}
    except Exception as e:
        return {"ok": False, "message": str(e)}

@router.get("/search")
async def test_search():
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text("测试", max_results=1))
            if results:
                return {"ok": True, "message": "联网搜索正常"}
            return {"ok": False, "message": "搜索无结果"}
    except Exception as e:
        return {"ok": False, "message": str(e)}

@router.get("/ip")
async def test_ip():
    """测试 IP 定位（三重尝试）"""
    import requests as req
    api_key = get_config("amap_key", "")
    # 1. 高德 IP
    if api_key:
        try:
            resp = req.get(f"https://restapi.amap.com/v3/ip?key={api_key}", timeout=5)
            data = resp.json()
            if data.get("status") == "1":
                p, c = data.get("province", ""), data.get("city", "")
                if isinstance(p, list): p = ""
                if isinstance(c, list): c = ""
                if c: return {"ok": True, "message": f"{p} {c}"}
        except: pass
    # 2. ip-api.com
    try:
        resp = req.get("http://ip-api.com/json/?lang=zh-CN", timeout=5)
        data = resp.json()
        if data.get("status") == "success": return {"ok": True, "message": f"{data.get('regionName','')} {data['city']}"}
    except: pass

    # 4. 用已配置的城市
    city = get_config("precise_city", "")
    if city: return {"ok": True, "message": f"手动设置: {city}"}

    return {"ok": False, "message": "所有定位方式均失败"}
