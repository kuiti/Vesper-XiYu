import os
import shutil
import requests
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from core.db import set_config, get_config

router = APIRouter(prefix="/avatar", tags=["avatar"])

AVATAR_DIR = "data/avatars"
os.makedirs(AVATAR_DIR, exist_ok=True)

class AvatarUrl(BaseModel):
    url: str

@router.post("/upload/{role}")
async def upload_avatar(role: str, file: UploadFile = File(...)):
    if role not in ["user", "assistant", "bg"]:
        raise HTTPException(400, "角色只能是 user、assistant 或 bg")

    # 删除旧头像
    old_avatar = get_config(f"avatar_{role}", "")
    if old_avatar:
        old_path = os.path.join(AVATAR_DIR, old_avatar)
        if os.path.exists(old_path):
            os.remove(old_path)

    # 校验文件类型
    allowed_types = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp"}
    if file.content_type and file.content_type not in allowed_types:
        raise HTTPException(400, f"不支持的文件类型: {file.content_type}，仅支持 JPEG/PNG/GIF/WebP/BMP")

    # 生成带时间戳的文件名
    ext = (file.filename or "unknown.png").split(".")[-1]
    if ext.lower() not in ("jpg", "jpeg", "png", "gif", "webp", "bmp"):
        ext = "png"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_filename = f"{role}_{timestamp}.{ext}"
    file_path = os.path.join(AVATAR_DIR, new_filename)

    # 限制 5MB，流式写入
    total = 0
    with open(file_path, "wb") as f:
        while chunk := file.file.read(8192):
            total += len(chunk)
            if total > 5 * 1024 * 1024:
                f.close()
                os.remove(file_path)
                raise HTTPException(400, "头像文件不能超过 5MB")
            f.write(chunk)

    set_config(f"avatar_{role}", new_filename)
    return {"filename": new_filename, "url": f"/avatars/{new_filename}"}

@router.post("/upload-url/{role}")
async def upload_avatar_by_url(role: str, data: AvatarUrl):
    if role not in ["user", "assistant"]:
        raise HTTPException(400, "角色只能是 user 或 assistant")

    from urllib.parse import urlparse
    import socket, ipaddress

    parsed = urlparse(data.url)
    if parsed.scheme not in ("https", "http"):
        raise HTTPException(400, "仅支持 http/https 链接")
    try:
        hostname = parsed.hostname
        ip = socket.gethostbyname(hostname)
    except Exception:
        raise HTTPException(400, "无法解析域名")
    try:
        addr = ipaddress.ip_address(ip)
        if addr.is_private or addr.is_loopback or addr.is_link_local:
            raise HTTPException(400, "不允许使用内网地址")
    except ValueError:
        pass

    try:
        resp = requests.get(data.url, timeout=10, stream=True)
        resp.raise_for_status()
    except Exception as e:
        raise HTTPException(400, f"下载图片失败: {e}")

    # 根据 Content-Type 确定扩展名
    content_type = resp.headers.get("content-type", "")
    if "png" in content_type:
        ext = "png"
    elif "gif" in content_type:
        ext = "gif"
    elif "webp" in content_type:
        ext = "webp"
    else:
        ext = "jpg"

    # 删除旧头像
    old_avatar = get_config(f"avatar_{role}", "")
    if old_avatar:
        old_path = os.path.join(AVATAR_DIR, old_avatar)
        if os.path.exists(old_path):
            os.remove(old_path)

    # 保存新头像
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_filename = f"{role}_{timestamp}.{ext}"
    file_path = os.path.join(AVATAR_DIR, new_filename)

    total = 0
    with open(file_path, "wb") as f:
        for chunk in resp.iter_content(8192):
            total += len(chunk)
            if total > 5 * 1024 * 1024:
                f.close()
                os.remove(file_path)
                raise HTTPException(400, "头像文件不能超过 5MB")
            f.write(chunk)

    set_config(f"avatar_{role}", new_filename)
    return {"filename": new_filename, "url": f"/avatars/{new_filename}"}

@router.get("/{role}")
async def get_avatar_url(role: str):
    filename = get_config(f"avatar_{role}", "")
    if not filename:
        return {"url": None}
    return {"url": f"/avatars/{filename}"}