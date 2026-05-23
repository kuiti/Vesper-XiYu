"""可插拔云端后端 —— WebDAV / S3 / 自定义 HTTP"""

import requests
from abc import ABC, abstractmethod


class CloudBackend(ABC):
    @abstractmethod
    def upload(self, data: bytes, path: str) -> bool:
        pass

    @abstractmethod
    def download(self, path: str) -> bytes:
        pass

    @abstractmethod
    def status(self) -> dict:
        pass


class WebDAVBackend(CloudBackend):
    def __init__(self, url: str, username: str = "", password: str = ""):
        self.url = url.rstrip("/")
        self.auth = (username, password) if username else None

    def upload(self, data: bytes, path: str) -> bool:
        try:
            from urllib.parse import quote
            r = requests.put(f"{self.url}/{quote(path, safe='/')}", data=data, auth=self.auth, timeout=30)
            return r.status_code in (200, 201, 204)
        except Exception as e:
            print(f"[WebDAV] 上传失败: {e}")
            return False

    def download(self, path: str) -> bytes:
        try:
            from urllib.parse import quote
            r = requests.get(f"{self.url}/{quote(path, safe='/')}", auth=self.auth, timeout=30)
            r.raise_for_status()
            return r.content
        except Exception as e:
            print(f"[WebDAV] 下载失败: {e}")
            raise

    def status(self) -> dict:
        try:
            r = requests.head(self.url, auth=self.auth, timeout=10)
            if r.status_code == 405:  # HEAD not supported, fallback to GET
                r = requests.get(self.url, auth=self.auth, timeout=10)
            return {"reachable": True, "status": r.status_code}
        except Exception as e:
            return {"reachable": False, "error": str(e)}


class CustomHTTPBackend(CloudBackend):
    def __init__(self, upload_url: str, download_url: str, headers: dict = None):
        self.upload_url = upload_url
        self.download_url = download_url
        self.headers = headers or {}

    def upload(self, data: bytes, path: str) -> bool:
        try:
            hdrs = dict(self.headers)
            hdrs["X-Backup-Path"] = path
            r = requests.post(self.upload_url, data=data, headers=hdrs, timeout=30)
            return r.status_code == 200
        except Exception as e:
            print(f"[HTTP] 上传失败: {e}")
            return False

    def download(self, path: str) -> bytes:
        try:
            r = requests.get(self.download_url, params={"path": path}, headers=self.headers, timeout=30)
            r.raise_for_status()
            return r.content
        except Exception as e:
            print(f"[HTTP] 下载失败: {e}")
            raise

    def status(self) -> dict:
        try:
            r = requests.head(self.upload_url, headers=self.headers, timeout=10)
            return {"reachable": True, "status": r.status_code}
        except Exception as e:
            return {"reachable": False, "error": str(e)}


def get_backend(backend_type: str, config: dict) -> CloudBackend:
    if backend_type == "webdav":
        return WebDAVBackend(config.get("url", ""), config.get("username", ""), config.get("password", ""))
    if backend_type == "custom":
        return CustomHTTPBackend(config.get("upload_url", ""), config.get("download_url", ""), config.get("headers", {}))
    raise ValueError(f"Unknown backend: {backend_type}")
