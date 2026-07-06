# core/retry.py — 通用重试工具 + silent_exc 辅助
"""提供带指数退避的重试装饰器和 silent_exc 快捷函数。"""
import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)


def silent_exc(ctx: str, e: BaseException) -> None:
    """静默记录非关键异常，统一格式。"""
    logger.warning("[%s] %s", ctx, e)


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 10.0,
                       exceptions: tuple = (Exception,)):
    """指数退避重试装饰器。

    Args:
        max_retries: 最大重试次数（不含首次）
        base_delay: 基础延迟秒数
        max_delay: 最大延迟秒数
        exceptions: 需要重试的异常类型元组
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        logger.warning("[retry] %s 第%d次失败: %s, %.1fs后重试",
                                       func.__name__, attempt + 1, e, delay)
                        time.sleep(delay)
                    else:
                        logger.error("[retry] %s 全部%d次重试失败: %s",
                                     func.__name__, max_retries + 1, e)
            raise last_exc
        return wrapper
    return decorator