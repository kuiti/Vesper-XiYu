# core/security.py — 安全防护模块
"""SSRF 防护 + 工具输入校验 + 配置白名单。

用法:
    from core.security import validate_request_url, sanitize_input
    if not validate_request_url("https://example.com/api"):
        return "拒绝请求：内网地址"
"""

from __future__ import annotations
import os
import socket
socket.setdefaulttimeout(3)
import ipaddress
import re
from urllib.parse import urlparse


# ─── SSRF 防护 ───

# 禁止访问的内网网段
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),       # loopback
    ipaddress.ip_network("10.0.0.0/8"),         # 私有 A 类
    ipaddress.ip_network("172.16.0.0/12"),      # 私有 B 类
    ipaddress.ip_network("192.168.0.0/16"),     # 私有 C 类
    ipaddress.ip_network("169.254.0.0/16"),     # link-local
    ipaddress.ip_network("::1/128"),             # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),            # IPv6 私有
    ipaddress.ip_network("fe80::/10"),           # IPv6 link-local
]

# 允许的协议白名单
_ALLOWED_SCHEMES = {"http", "https"}


def validate_request_url(url: str) -> bool:
    """验证 URL 是否可安全请求（防 SSRF）。

    检查:
        1. 协议是否允许 (http/https)
        2. DNS 解析后的 IP 是否为内网地址
        3. 是否指向 localhost

    Returns:
        True: 允许请求
        False: 拒绝请求
    """
    if not url or not isinstance(url, str):
        return False

    parsed = urlparse(url)
    scheme = parsed.scheme.lower()

    # 协议校验
    if scheme not in _ALLOWED_SCHEMES:
        return False

    host = parsed.hostname
    if not host:
        return False

    # 直接检查常见的内网 hostname
    host_lower = host.lower()
    if host_lower in ("localhost", "localhost.localdomain", "127.0.0.1", "::1", "0.0.0.0"):
        return False
    if host_lower.endswith(".local") or host_lower.endswith(".internal"):
        return False

    # DNS 解析检查
    try:
        ips = socket.getaddrinfo(host, parsed.port or 443)
        for family, type_, proto, canonname, sockaddr in ips:
            ip_str = sockaddr[0]
            try:
                ip = ipaddress.ip_address(ip_str)
                for net in _PRIVATE_NETWORKS:
                    if ip in net:
                        return False
            except ValueError:
                continue  # 忽略无法解析的 IP
        return True
    except socket.gaierror:
        # DNS 解析失败时，保守拒绝
        return False
    except Exception:
        return False


# ─── 输入校验 ───

# SQL 注入模式（仅用于日志告警，不用于阻止——参数化查询已免疫）
_SQL_INJECTION_PATTERNS = [
    re.compile(r"'.*OR.*'.*'.*", re.IGNORECASE),
    re.compile(r"';.*--", re.IGNORECASE),
    re.compile(r"UNION.*SELECT", re.IGNORECASE),
    re.compile(r"DROP\s+TABLE", re.IGNORECASE),
    re.compile(r"DELETE\s+FROM", re.IGNORECASE),
]

# 路径遍历模式
_PATH_TRAVERSAL_PATTERN = re.compile(
    r"\.\./|\.\.\\|\.\.%2f|\.\.%5c|%2e%2e[/\\]|%00|\.\.%252f|\.\.%255c",
    re.IGNORECASE
)


def detect_sql_injection(text: str) -> bool:
    """检测 SQL 注入模式（参数化查询已免疫，此函数仅用于日志告警）"""
    if not text:
        return False
    for pattern in _SQL_INJECTION_PATTERNS:
        if pattern.search(text):
            return True
    return False


def detect_path_traversal(path: str) -> bool:
    """检测路径遍历攻击"""
    if not path:
        return False
    return bool(_PATH_TRAVERSAL_PATTERN.search(path))


def sanitize_filename(filename: str) -> str:
    """清理文件名，移除危险字符"""
    # 只保留字母数字、中文、连字符、下划线、点
    clean = re.sub(r'[^\w\s\-_.一-鿿]', '', filename)
    # 防止空文件名
    return clean.strip() or "unnamed"


def sanitize_display_text(text: str, max_length: int = 5000) -> str:
    """清理显示文本，防止 XSS 和过长文本"""
    if not text:
        return ""
    # 移除 HTML 标签（用户可见文本不应含 HTML）
    clean = re.sub(r'<[^>]*>', '', text)
    # 截断
    if len(clean) > max_length:
        clean = clean[:max_length] + "..."
    return clean


def validate_path_within(base_dir: str, target_path: str) -> bool:
    """验证 target_path 是否在 base_dir 内（防路径穿越）。

    Returns:
        True: 安全
        False: 路径穿越或无效
    """
    try:
        base = os.path.realpath(base_dir)
        target = os.path.realpath(target_path)
        return target.startswith(base + os.sep) or target == base
    except (ValueError, OSError):
        return False


def sanitize_path_component(name: str) -> str:
    """清理路径中的单个组件（文件名/目录名），移除危险字符"""
    if not name:
        return ""
    # 移除路径分隔符和 .. 
    clean = name.replace("/", "").replace("\\", "").replace("..", "")
    # 只保留安全字符
    clean = re.sub(r'[^\w\s\-_.一-鿿]', '', clean)
    return clean.strip() or "unnamed"
