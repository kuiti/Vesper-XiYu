import requests
from fastapi import APIRouter, HTTPException
from core.db import get_config
from pydantic import BaseModel

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
    resp = requests.get(url, timeout=10)
    data = resp.json()
    if data.get("status") == "1":
        provinces = []
        for item in data["districts"][0]["districts"]:
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
    resp = requests.get(url, timeout=10)
    data = resp.json()
    if data.get("status") == "1" and data["districts"]:
        cities = []
        for item in data["districts"][0]["districts"]:
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
    resp = requests.get(url, timeout=10)
    data = resp.json()
    if data.get("status") == "1" and data["districts"]:
        districts = []
        for item in data["districts"][0]["districts"]:
            districts.append({"name": item["name"], "adcode": item["adcode"]})
        return districts
    raise HTTPException(500, "获取区县失败")

@router.get("/ip")
async def get_location_by_ip():
    """通过 IP 获取当前城市（高德优先，失败则用备用服务）"""
    key = get_config("amap_key", "")
    if key:
        try:
            resp = requests.get(f"https://restapi.amap.com/v3/ip?key={key}", timeout=10)
            data = resp.json()
            if data.get("status") == "1":
                province = data.get("province", "")
                city = data.get("city", "")
                # 高德可能返回空数组 [] 表示无法定位
                if isinstance(province, list): province = ""
                if isinstance(city, list): city = ""
                if city:
                    return {"province": province, "city": city, "adcode": data.get("adcode", "")}
        except:
            pass

    # 备用: ip-api.com
    try:
        resp = requests.get("http://ip-api.com/json/?lang=zh-CN", timeout=5)
        data = resp.json()
        if data.get("status") == "success":
            return {"province": data.get("regionName", ""), "city": data.get("city", ""), "adcode": ""}
    except:
        pass

    return {"province": "", "city": "", "adcode": ""}

@router.post("/geo")
async def reverse_geocode(coord: GeoCoord):
    """浏览器精确定位：坐标 → 地址（米级精度）"""
    key = get_config("amap_key", "")
    if not key:
        raise HTTPException(400, "请先配置高德 API Key")
    try:
        url = f"https://restapi.amap.com/v3/geocode/regeo?key={key}&location={coord.lng},{coord.lat}&extensions=base"
        resp = requests.get(url, timeout=10)
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