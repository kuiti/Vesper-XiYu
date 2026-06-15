"""云端同步 API —— 端到端加密备份上传/下载"""

import asyncio
from fastapi import APIRouter
from pydantic import BaseModel
from core.db import get_config, set_config
import json
from datetime import datetime

router = APIRouter(prefix="/cloud", tags=["cloud"])


class CloudConfig(BaseModel):
    backend_type: str = ""       # "webdav" / "custom"
    url: str = ""
    username: str = ""
    password: str = ""
    upload_url: str = ""
    download_url: str = ""
    passphrase: str = ""         # 加密密码
    auto_sync: bool = False
    auto_interval: int = 1440    # 分钟


@router.get("/config")
async def get_cloud_config():
    return {"config": get_config("cloud_config", {})}


@router.post("/config")
async def save_cloud_config(cfg: CloudConfig):
    config_dict = cfg.model_dump()
    passphrase = config_dict.pop("passphrase", None)
    if passphrase:
        from core.crypto import derive_key
        key, salt = derive_key(passphrase)
        config_dict["passphrase_salt"] = salt.hex()
        config_dict["passphrase_key"] = key.hex()
    set_config("cloud_config", config_dict)
    return {"status": "ok"}


@router.get("/status")
async def sync_status():
    last = get_config("cloud_last_sync", "")
    return {
        "last_sync": last or "从未同步",
        "crypto_available": _check_crypto()
    }


@router.post("/upload")
async def upload_backup(passphrase: str = ""):
    cfg = get_config("cloud_config", {})
    if not cfg:
        return {"status": "error", "message": "请先配置云端后端"}

    try:
        from core.cloud_backends import get_backend
        from api.migrate import _collect_export_data
        backend = get_backend(cfg.get("backend_type", "webdav"), cfg)

        data = json.dumps(_collect_export_data(), ensure_ascii=False)

        # 优先使用已存储的密钥，否则从 passphrase 派生
        stored_salt = cfg.get("passphrase_salt", "")
        stored_key = cfg.get("passphrase_key", "")
        if stored_salt and stored_key:
            from core.crypto import encrypt_data
            salt = bytes.fromhex(stored_salt)
            key = bytes.fromhex(stored_key)
            encrypted = encrypt_data(data, key)
            payload = salt + encrypted.encode()
        elif passphrase:
            from core.crypto import encrypt_data, derive_key
            key, salt = derive_key(passphrase)
            encrypted = encrypt_data(data, key)
            payload = salt + encrypted.encode()
        else:
            payload = data.encode()

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        ok = await asyncio.to_thread(backend.upload, payload, f"vesper_backup_{ts}.enc")
        if ok:
            set_config("cloud_last_sync", datetime.now().isoformat())
            return {"status": "ok", "filename": f"vesper_backup_{ts}.enc"}
        return {"status": "error", "message": "上传失败"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/download")
async def download_backup(filename: str = "", passphrase: str = ""):
    cfg = get_config("cloud_config", {})
    if not cfg:
        return {"status": "error", "message": "请先配置云端后端"}

    try:
        from core.cloud_backends import get_backend
        backend = get_backend(cfg.get("backend_type", "webdav"), cfg)

        if not filename:
            filename = "vesper_backup_latest.enc"

        raw = await asyncio.to_thread(backend.download, filename)

        # 优先使用已存储的密钥，否则从 passphrase 派生
        stored_salt = cfg.get("passphrase_salt", "")
        stored_key = cfg.get("passphrase_key", "")
        if stored_salt and stored_key:
            from core.crypto import decrypt_data
            salt, encrypted = raw[:16], raw[16:]
            key = bytes.fromhex(stored_key)
            data = decrypt_data(encrypted.decode(), key)
        elif passphrase:
            from core.crypto import decrypt_data, derive_key
            salt, encrypted = raw[:16], raw[16:]
            key, _ = derive_key(passphrase, salt)
            data = decrypt_data(encrypted.decode(), key)
        else:
            data = raw.decode()

        return {"status": "ok", "data": json.loads(data)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/test")
async def test_connection():
    cfg = get_config("cloud_config", {})
    if not cfg:
        return {"status": "error", "message": "未配置"}
    try:
        from core.cloud_backends import get_backend
        backend = get_backend(cfg.get("backend_type", "webdav"), cfg)
        result = await asyncio.to_thread(backend.status)
        return {"status": "ok", **result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _check_crypto():
    try:
        from core.crypto import is_crypto_available
        return is_crypto_available()
    except Exception:
        return False
