"""头像管理 API —— 支持上传、URL 导入和查询用户/AI 头像。"""
import os
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from core.db import set_config, get_config
from core.retry import silent_exc

router = APIRouter(prefix="/avatar", tags=["avatar"])

AVATAR_DIR = "data/avatars"
os.makedirs(AVATAR_DIR, exist_ok=True)

class AvatarUrl(BaseModel):
    url: str

@router.post("/upload/{role}")
async def upload_avatar(role: str, file: UploadFile = File(...)):
    """上传头像文件（支持 user/assistant/bg 角色）。"""
    if role not in ["user", "assistant", "bg"]:
        raise HTTPException(400, "角色只能是 user、assistant 或 bg")

    # 校验文件类型（允许 application/octet-stream，通过扩展名判断）
    allowed_types = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp", "application/octet-stream"}
    if file.content_type and file.content_type not in allowed_types:
        raise HTTPException(400, f"不支持的文件类型: {file.content_type}，仅支持 JPEG/PNG/GIF/WebP/BMP")

    # 生成带时间戳的文件名
    safe_name = os.path.basename(file.filename or "unknown.png")
    ext = safe_name.split(".")[-1] if "." in safe_name else "png"
    if "/" in ext or "\\" in ext or ".." in ext:
        ext = "png"
    if ext.lower() not in ("jpg", "jpeg", "png", "gif", "webp", "bmp"):
        ext = "png"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_filename = f"{role}_{timestamp}.{ext}"
    file_path = os.path.join(AVATAR_DIR, new_filename)

    # 先写临时文件，成功后再替换旧头像
    tmp_path = file_path + ".tmp"
    total = 0
    try:
        with open(tmp_path, "wb") as f:
            while chunk := file.file.read(8192):
                total += len(chunk)
                if total > 5 * 1024 * 1024:
                    raise HTTPException(400, "头像文件不能超过 5MB")
                f.write(chunk)
    except HTTPException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    # 成功：删除旧头像，重命名临时文件
    from core.security import validate_path_within
    old_avatar = get_config(f"avatar_{role}", "")
    if old_avatar:
        old_avatar_safe = os.path.basename(old_avatar)
        old_path = os.path.join(AVATAR_DIR, old_avatar_safe)
        if os.path.exists(old_path) and validate_path_within(AVATAR_DIR, old_path):
            os.remove(old_path)
    os.rename(tmp_path, file_path)

    set_config(f"avatar_{role}", new_filename)
    return {"filename": new_filename, "url": f"/avatars/{new_filename}"}

@router.post("/upload-url/{role}")
async def upload_avatar_by_url(role: str, data: AvatarUrl):
    """通过 URL 下载并设置头像（含 SSRF 防护）。"""
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
    except Exception as e:
        silent_exc("avatar", e)

    # DNS 重绑定防护：用解析后的 IP 替换 hostname，防止第二次解析到不同地址
    safe_url = data.url.replace(hostname, ip, 1) if hostname else data.url
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(safe_url, headers={"Host": hostname}, follow_redirects=True)
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

    # 保存新头像（先保存，成功后再删旧的）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_filename = f"{role}_{timestamp}.{ext}"
    file_path = os.path.join(AVATAR_DIR, new_filename)
    old_avatar = get_config(f"avatar_{role}", "")

    total = 0
    with open(file_path, "wb") as f:
        for chunk in resp.iter_content(8192):
            total += len(chunk)
            if total > 5 * 1024 * 1024:
                f.close()
                os.remove(file_path)
                raise HTTPException(400, "头像文件不能超过 5MB")
            f.write(chunk)

    # 删除旧头像（新头像保存成功后）
    from core.security import validate_path_within
    if old_avatar:
        old_avatar_safe = os.path.basename(old_avatar)
        old_path = os.path.join(AVATAR_DIR, old_avatar_safe)
        if os.path.exists(old_path) and validate_path_within(AVATAR_DIR, old_path):
            os.remove(old_path)

    set_config(f"avatar_{role}", new_filename)
    return {"filename": new_filename, "url": f"/avatars/{new_filename}"}

@router.get("/{role}")
async def get_avatar_url(role: str):
    """获取指定角色的头像 URL，支持多级回退。"""
    import json as _json
    filename = get_config(f"avatar_{role}", "")
    if not filename:
        # 回退到默认头像
        avatars = get_config("avatars", "")
        if avatars:
            if isinstance(avatars, dict):
                default = avatars.get(role, "")
            elif isinstance(avatars, str):
                try:
                    default = _json.loads(avatars).get(role, "")
                except _json.JSONDecodeError:
                    default = ""
            else:
                default = ""
            if default and os.path.exists(os.path.join(AVATAR_DIR, default)):
                return {"url": f"/avatars/{default}"}
        # 硬回退：检查默认文件名
        for ext in ("jpg", "jpeg", "png"):
            df = f"{role}_default.{ext}"
            if os.path.exists(os.path.join(AVATAR_DIR, df)):
                return {"url": f"/avatars/{df}"}
        return {"url": None}
    return {"url": f"/avatars/{filename}"}