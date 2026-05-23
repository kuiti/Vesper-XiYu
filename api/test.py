import asyncio
import requests
from fastapi import APIRouter
from core.db import get_config

router = APIRouter(prefix="/test", tags=["test"])

@router.get("/models")
async def fetch_models():
    """获取可用模型列表（支持 Ollama / OpenAI 兼容）"""
    api_key = get_config("api_key", "")
    base_url = get_config("api_base_url", "https://api.deepseek.com/v1").rstrip("/")
    is_ollama = get_config("api_provider", "") == "ollama" or "localhost:11434" in base_url
    if not api_key and not is_ollama:
        return {"ok": False, "models": [], "message": "未配置 API Key"}
    try:
        if is_ollama:
            # Ollama 用 /api/tags 获取模型列表（从 base_url 提取 host:port）
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            ollama_host = f"{parsed.scheme}://{parsed.netloc}"
            resp = await asyncio.to_thread(requests.get, f"{ollama_host}/api/tags", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            models = [m["name"] for m in data.get("models", [])]
            models.sort()
        else:
            headers = {"Authorization": f"Bearer {api_key}"}
            resp = await asyncio.to_thread(requests.get, f"{base_url}/models", headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            models = [m["id"] for m in data.get("data", [])]
            models.sort()
        return {"ok": True, "models": models}
    except Exception as e:
        return {"ok": False, "models": [], "message": str(e)}

@router.get("/deepseek")
async def test_deepseek():
    api_key = get_config("api_key", "")
    base_url = get_config("api_base_url", "https://api.deepseek.com/v1").rstrip("/")
    is_ollama = get_config("api_provider", "") == "ollama" or "localhost:11434" in base_url
    if not api_key and not is_ollama:
        return {"ok": False, "message": "未配置 API Key"}
    try:
        model = get_config("api_model", "deepseek-chat")
        if is_ollama and not api_key:
            headers = {"Content-Type": "application/json"}
        else:
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "回复OK即可"}],
            "max_tokens": 5,
            "temperature": 0
        }
        resp = await asyncio.to_thread(requests.post, f"{base_url}/chat/completions", headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        return {"ok": True, "message": f"{model} API 正常"}
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
        def _search():
            with DDGS() as ddgs:
                return list(ddgs.text("测试", max_results=1))
        results = await asyncio.to_thread(_search)
        if results:
            return {"ok": True, "message": "联网搜索正常"}
        return {"ok": False, "message": "搜索无结果"}
    except Exception as e:
        return {"ok": False, "message": str(e)}

@router.get("/ip")
async def test_ip():
    """测试 IP 定位（三重尝试）"""
    api_key = get_config("amap_key", "")
    # 1. 高德 IP
    if api_key:
        try:
            resp = await asyncio.to_thread(requests.get, f"https://restapi.amap.com/v3/ip?key={api_key}", timeout=5)
            data = resp.json()
            if data.get("status") == "1":
                p, c = data.get("province", ""), data.get("city", "")
                if isinstance(p, list): p = ""
                if isinstance(c, list): c = ""
                if c: return {"ok": True, "message": f"{p} {c}"}
        except Exception as e:
            print(f"[测试IP] 高德异常: {e}")
    # 2. ip-api.com
    try:
        resp = await asyncio.to_thread(requests.get, "http://ip-api.com/json/?lang=zh-CN", timeout=5)
        data = resp.json()
        if data.get("status") == "success": return {"ok": True, "message": f"{data.get('regionName','')} {data['city']}"}
    except Exception as e:
        print(f"[测试IP] ip-api 异常: {e}")

    # 3. 用已配置的城市
    city = get_config("precise_city", "")
    if city: return {"ok": True, "message": f"手动设置: {city}"}

    return {"ok": False, "message": "所有定位方式均失败"}
