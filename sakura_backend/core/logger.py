# core/logger.py — 统一日志模块
"""
用法：
    from core.logger import get_logger
    logger = get_logger("chat")
    logger.info("用户消息: %s", content[:50])

替代散落的 print()，支持：
- 文件轮转（10MB × 5 个备份）
- 控制台彩色输出
- 按模块分级过滤
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

_LOG_DIR = "data/logs"
os.makedirs(_LOG_DIR, exist_ok=True)

# 全局配置
_LOG_LEVEL = os.environ.get("SAKURA_LOG_LEVEL", "INFO").upper()
_LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_root_configured = False

def _ensure_root():
    """延迟配置根 logger，只执行一次"""
    global _root_configured
    if _root_configured:
        return
    _root_configured = True

    root = logging.getLogger("sakura")
    root.setLevel(getattr(logging, _LOG_LEVEL, logging.INFO))

    # 控制台输出
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
    root.addHandler(console)

    # 文件输出（轮转：10MB × 5 个）
    file_handler = RotatingFileHandler(
        os.path.join(_LOG_DIR, "sakura.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
    root.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """获取模块 logger，如 get_logger('chat') → sakura.chat"""
    _ensure_root()
    return logging.getLogger(f"sakura.{name}")
