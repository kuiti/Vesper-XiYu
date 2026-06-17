import asyncio
import logging

import requests
from fastapi import APIRouter, HTTPException, Request
from core.db import get_config
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/location", tags=["location"])

class GeoCoord(BaseModel):
    lat: float
    lng: float

@router.get("/provinces")
async def get_provinces():
    """获取所有省份（一级行政区）"""
    key = get_config("amap_key", "")
    if not key:
        raise HTTPException(400, "请先配置高德 API Key")
    url = f"https://restapi.amap.com/v3/config/district?keywords=中国&subdistrict=1&key={key}"
    try:
        resp = await asyncio.to_thread(requests.get, url, timeout=10)
        data = resp.json()
    except Exception as e:
        raise HTTPException(502, f"请求高德API失败: {e}")
    if data.get("status") == "1" and data.get("districts") and len(data["districts"]) > 0:
        provinces = []
        for item in data["districts"][0].get("districts", []):
            provinces.append({"name": item["name"], "adcode": item["adcode"]})
        return provinces
    raise HTTPException(500, "获取省份失败")

@router.get("/cities/{province_adcode}")
async def get_cities(province_adcode: str):
    """根据省份 adcode 获取城市列表"""
    key = get_config("amap_key", "")
    if not key:
        raise HTTPException(400, "请先配置高德 API Key")
    url = f"https://restapi.amap.com/v3/config/district?keywords={province_adcode}&subdistrict=1&key={key}"
    try:
        resp = await asyncio.to_thread(requests.get, url, timeout=10)
        data = resp.json()
    except Exception as e:
        raise HTTPException(502, f"请求高德API失败: {e}")
    if data.get("status") == "1" and data.get("districts") and len(data["districts"]) > 0:
        cities = []
        for item in data["districts"][0].get("districts", []):
            cities.append({"name": item["name"], "adcode": item["adcode"]})
        return cities
    raise HTTPException(500, "获取城市失败")

@router.get("/districts/{city_adcode}")
async def get_districts(city_adcode: str):
    """根据城市 adcode 获取区/县列表"""
    key = get_config("amap_key", "")
    if not key:
        raise HTTPException(400, "请先配置高德 API Key")
    url = f"https://restapi.amap.com/v3/config/district?keywords={city_adcode}&subdistrict=1&key={key}"
    try:
        resp = await asyncio.to_thread(requests.get, url, timeout=10)
        data = resp.json()
    except Exception as e:
        raise HTTPException(502, f"请求高德API失败: {e}")
    if data.get("status") == "1" and data.get("districts") and len(data["districts"]) > 0:
        districts = []
        for item in data["districts"][0].get("districts", []):
            districts.append({"name": item["name"], "adcode": item["adcode"]})
        return districts
    raise HTTPException(500, "获取区县失败")

@router.get("/ip")
async def get_location_by_ip(request: Request):
    """通过 IP 获取当前城市（高德优先，失败则用备用服务）"""
    # 获取客户端真实 IP
    client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if not client_ip:
        client_ip = request.headers.get("X-Real-IP", "")
    if not client_ip:
        client_ip = request.client.host if request.client else ""

    key = get_config("amap_key", "")
    if key:
        try:
            # 传入客户端 IP
            url = f"https://restapi.amap.com/v3/ip?key={key}&ip={client_ip}" if client_ip else f"https://restapi.amap.com/v3/ip?key={key}"
            resp = await asyncio.to_thread(requests.get, url, timeout=10)
            data = resp.json()
            if data.get("status") == "1":
                province = data.get("province", "")
                city = data.get("city", "")
                if isinstance(province, list): province = ""
                if isinstance(city, list): city = ""
                if city:
                    return {"province": province, "city": city, "adcode": data.get("adcode", "")}
        except Exception as e:
            logger.warning(f"[定位] 异常: {e}")

    # 备用: ip-api.com（用客户端 IP）
    try:
        if client_ip:
            url = f"https://ip-api.com/json/{client_ip}?lang=zh-CN"
        else:
            url = f"https://ip-api.com/json/?lang=zh-CN"
        resp = await asyncio.to_thread(requests.get, url, timeout=5)
        data = resp.json()
        if data.get("status") == "success":
            return {"province": data.get("regionName", ""), "city": data.get("city", ""), "adcode": ""}
    except Exception as e:
        logger.warning(f"[定位] ip-api 异常: {e}")

    return {"province": "", "city": "", "adcode": ""}

@router.post("/geo")
async def reverse_geocode(coord: GeoCoord):
    """浏览器精确定位：坐标 → 地址（米级精度）"""
    key = get_config("amap_key", "")
    if not key:
        raise HTTPException(400, "请先配置高德 API Key")
    try:
        url = f"https://restapi.amap.com/v3/geocode/regeo?key={key}&location={coord.lng},{coord.lat}&extensions=base"
        resp = await asyncio.to_thread(requests.get, url, timeout=10)
        data = resp.json()
        if data.get("status") == "1":
            addr = data.get("regeocode", {}).get("addressComponent", {})
            return {
                "province": addr.get("province", ""),
                "city": addr.get("city", "") or addr.get("province", ""),
                "district": addr.get("district", ""),
                "township": addr.get("township", ""),
                "street": addr.get("streetNumber", {}).get("street", ""),
                "detail": data.get("regeocode", {}).get("formatted_address", "")
            }
        return {"error": data.get("info", "逆地理编码失败")}
    except Exception as e:
        raise HTTPException(500, str(e))
