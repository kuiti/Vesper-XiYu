"""多模态图片理解 —— 基础设施就绪，等待 API 提供商支持视觉模型"""

from fastapi import APIRouter, UploadFile, File
import base64, os

router = APIRouter(prefix="/vision", tags=["vision"])

UPLOAD_DIR = os.path.join("data", "vision")
os.makedirs(UPLOAD_DIR, exist_ok=True)

_ALLOWED_VISION_MIME = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp"}


@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    """上传图片，返回 base64 数据供后续视觉 API 调用"""
    if not file.filename:
        return {"status": "error", "message": "未选择文件"}
    safe_name = os.path.basename(file.filename)
    if not safe_name or safe_name.startswith('.') or safe_name != file.filename:
        return {"status": "error", "message": "文件名不合法"}
    if file.content_type and file.content_type not in _ALLOWED_VISION_MIME:
        return {"status": "error", "message": "不支持的图片格式，仅支持 PNG/JPEG/GIF/WebP/BMP"}
    filepath = os.path.join(UPLOAD_DIR, safe_name)
    total_bytes = 0
    try:
        with open(filepath, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > 10 * 1024 * 1024:
                    f.close()
                    os.remove(filepath)
                    return {"status": "error", "message": "图片大小不能超过10MB"}
                f.write(chunk)
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return {"status": "error", "message": "图片上传失败"}
    with open(filepath, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return {"status": "ok", "filename": file.filename, "base64": b64,
            "mime": file.content_type or "image/png"}
