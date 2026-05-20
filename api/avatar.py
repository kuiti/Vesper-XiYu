import os
import shutil
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException
from core.db import set_config, get_config

router = APIRouter(prefix="/avatar", tags=["avatar"])

AVATAR_DIR = "data/avatars"
os.makedirs(AVATAR_DIR, exist_ok=True)

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
    
    # 生成带时间戳的文件名
    ext = (file.filename or "unknown.png").split(".")[-1]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_filename = f"{role}_{timestamp}.{ext}"
    file_path = os.path.join(AVATAR_DIR, new_filename)
    
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    set_config(f"avatar_{role}", new_filename)
    return {"filename": new_filename}

@router.get("/{role}")
async def get_avatar_url(role: str):
    filename = get_config(f"avatar_{role}", "")
    if not filename:
        return {"url": None}
    return {"url": f"/avatars/{filename}"}