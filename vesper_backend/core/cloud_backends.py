"""可插拔云端后端 —— WebDAV / S3 / 自定义 HTTP"""

import requests
import logging
from abc import ABC, abstractmethod
from core.security import validate_request_url

logger = logging.getLogger(__name__)


class CloudBackend(ABC):
    """云端存储后端抽象基类"""

    @abstractmethod
    def upload(self, data: bytes, path: str) -> bool:
        """上传数据到指定路径"""

    @abstractmethod
    def download(self, path: str) -> bytes:
        """从指定路径下载数据"""

    @abstractmethod
    def status(self) -> dict:
        """检查后端连接状态"""


class WebDAVBackend(CloudBackend):
    """WebDAV 协议云存储后端"""

    def __init__(self, url: str, username: str = "", password: str = ""):
        if not validate_request_url(url):
            raise ValueError(f"WebDAV URL 未通过安全校验: {url}")
        self.url = url.rstrip("/")
        self.auth = (username, password) if username else None

    def upload(self, data: bytes, path: str) -> bool:
        """通过 PUT 上传文件到 WebDAV 服务器"""
        try:
            from urllib.parse import quote
            r = requests.put(f"{self.url}/{quote(path, safe='/')}", data=data, auth=self.auth, timeout=30)
            return r.status_code in (200, 201, 204)
        except Exception as e:
            logger.warning(f"[WebDAV] 上传失败: {e}")
            return False

    def download(self, path: str) -> bytes:
        """从 WebDAV 服务器下载文件"""
        try:
            from urllib.parse import quote
            r = requests.get(f"{self.url}/{quote(path, safe='/')}", auth=self.auth, timeout=30)
            r.raise_for_status()
            return r.content
        except Exception as e:
            logger.warning(f"[WebDAV] 下载失败: {e}")
            raise

    def status(self) -> dict:
        """检测 WebDAV 服务器是否可达"""
        try:
            r = requests.head(self.url, auth=self.auth, timeout=10)
            if r.status_code == 405:  # HEAD not supported, fallback to GET
                r = requests.get(self.url, auth=self.auth, timeout=10)
            return {"reachable": True, "status": r.status_code}
        except Exception as e:
            return {"reachable": False, "error": str(e)}


class CustomHTTPBackend(CloudBackend):
    """自定义 HTTP 后端，通过 POST 上传、GET 下载"""

    def __init__(self, upload_url: str, download_url: str, headers: dict = None):
        # SSRF 防护：校验 URL 安全性
        if upload_url and not validate_request_url(upload_url):
            raise ValueError(f"upload_url 不安全: {upload_url}")
        if download_url and not validate_request_url(download_url):
            raise ValueError(f"download_url 不安全: {download_url}")
        self.upload_url = upload_url
        self.download_url = download_url
        self.headers = headers or {}

    def upload(self, data: bytes, path: str) -> bool:
        """通过 POST 上传数据，路径通过 X-Backup-Path 头传递"""
        try:
            hdrs = dict(self.headers)
            hdrs["X-Backup-Path"] = path
            r = requests.post(self.upload_url, data=data, headers=hdrs, timeout=30)
            return r.status_code == 200
        except Exception as e:
            logger.warning(f"[HTTP] 上传失败: {e}")
            return False

    def download(self, path: str) -> bytes:
        """通过 GET 下载数据，路径作为查询参数"""
        try:
            r = requests.get(self.download_url, params={"path": path}, headers=self.headers, timeout=30)
            r.raise_for_status()
            return r.content
        except Exception as e:
            logger.warning(f"[HTTP] 下载失败: {e}")
            raise

    def status(self) -> dict:
        """检测上传端点是否可达"""
        try:
            r = requests.head(self.upload_url, headers=self.headers, timeout=10)
            return {"reachable": True, "status": r.status_code}
        except Exception as e:
            return {"reachable": False, "error": str(e)}


def get_backend(backend_type: str, config: dict) -> CloudBackend:
    """根据类型和配置创建对应的云存储后端实例"""
    if backend_type == "webdav":
        return WebDAVBackend(config.get("url", ""), config.get("username", ""), config.get("password", ""))
    if backend_type == "custom":
        return CustomHTTPBackend(config.get("upload_url", ""), config.get("download_url", ""), config.get("headers", {}))
    raise ValueError(f"Unknown backend: {backend_type}")
