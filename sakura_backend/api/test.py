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
    """独立测试所有天气源，互不跳过"""
    city = get_config("precise_city") or get_config("manual_city") or get_config("default_city") or "北京"
    results = []

    # ── 1. 大模型联网：勾选了就测，未勾选注明 ──
    llm_weather = get_config("enable_llm_weather_search", False)
    if not llm_weather:
        results.append({"source": "大模型联网", "ok": False, "reason": "未勾选「使用大模型联网查询天气」"})
    else:
        api_key = get_config("api_key", "")
        base_url = get_config("api_base_url", "https://api.deepseek.com/v1").rstrip("/")
        if not api_key:
            results.append({"source": "大模型联网", "ok": False, "reason": "未配置 API Key"})
        else:
            try:
                model = get_config("api_model", "deepseek-chat")
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": f"{city}今天天气怎么样？用中文一句话回答，包含温度和天气状况。"}],
                    "max_tokens": 100, "temperature": 0.3, "stream": False,
                    "search": True,
                }
                resp = await asyncio.to_thread(
                    requests.post, f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=payload, timeout=25
                )
                resp.raise_for_status()
                body = resp.json()
                content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
                ok = bool(content and len(content.strip()) > 2)
                results.append({"source": "大模型联网", "ok": ok,
                    "reason": "API 响应正常" if ok else "响应为空（模型可能不支持 search 参数，或需在聊天偏好中开启联网策略）",
                    "preview": content.strip()[:120] if ok else ""})
            except Exception as e:
                results.append({"source": "大模型联网", "ok": False, "reason": f"调用失败: {str(e)[:100]}"})

    # ── 2. wttr.in：始终独立测试 ──
    try:
        from core.weather import get_wttr_weather
        w = await asyncio.to_thread(get_wttr_weather, city)
        if "error" not in w and w.get("temp") is not None:
            results.append({"source": "wttr.in", "ok": True, "reason": f'{w["weather"]} {w["temp"]}°C，湿度{w.get("humidity","?")}%'})
        else:
            results.append({"source": "wttr.in", "ok": False, "reason": w.get("error", "无数据") or "API 返回空"})
    except Exception as e:
        results.append({"source": "wttr.in", "ok": False, "reason": str(e)[:100]})

    # ── 3. Open-Meteo：始终独立测试 ──
    try:
        from api.intent import get_city_coords, get_openmeteo_weather
        coords = await asyncio.to_thread(get_city_coords, city)
        if coords:
            om = await asyncio.to_thread(get_openmeteo_weather, coords["lat"], coords["lng"])
            if "error" not in om and om.get("temp") is not None:
                results.append({"source": "Open-Meteo", "ok": True, "reason": f'{om["weather"]} {om["temp"]}°C，湿度{om.get("humidity","?")}%'})
            else:
                results.append({"source": "Open-Meteo", "ok": False, "reason": om.get("error", "无数据") or "API 返回空"})
        else:
            results.append({"source": "Open-Meteo", "ok": False, "reason": f'无法解析城市「{city}」的坐标'})
    except Exception as e:
        results.append({"source": "Open-Meteo", "ok": False, "reason": str(e)[:100]})

    # ── 4. 高德 ──
    amap_key = get_config("amap_key", "")
    if not amap_key:
        results.append({"source": "高德地图", "ok": False, "reason": "未配置高德 API Key"})
    else:
        try:
            url = f"https://restapi.amap.com/v3/weather/weatherInfo?key={amap_key}&city={city}&extensions=base"
            resp = await asyncio.to_thread(requests.get, url, timeout=10)
            data = resp.json()
            if data.get("status") == "1" and data.get("lives"):
                live = data["lives"][0]
                results.append({"source": "高德地图", "ok": True, "reason": f'{live.get("weather","")} {live.get("temperature","")}°C'})
            else:
                results.append({"source": "高德地图", "ok": False, "reason": data.get("info", "获取失败")})
        except Exception as e:
            results.append({"source": "高德地图", "ok": False, "reason": str(e)[:100]})

    ok_count = sum(1 for r in results if r["ok"])
    return {"ok": ok_count > 0, "city": city, "sources": results, "summary": f"{ok_count}/{len(results)} 个天气源可用"}

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
