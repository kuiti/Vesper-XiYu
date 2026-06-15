# core/db/config.py  |  config 表 CRUD

import json
import copy
import time as _time
from . import get_conn
from core.retry import silent_exc

# ========== 配置缓存 ==========
_config_cache = {}  # {key: (value, expire_ts)}
_CONFIG_TTL = 30.0  # 30 秒缓存，平衡响应速度与 DB 压力
_CONFIG_CACHE_MAX = 500


def clear_config_cache():
    """清除整个配置缓存（重置等批量操作后调用）"""
    _config_cache.clear()


def get_config(key, default=None):
    # 内存缓存命中
    now = _time.time()
    cached = _config_cache.get(key)
    if cached and cached[1] > now:
        v = cached[0]
        # 返回深拷贝，防止调用方修改缓存中的可变对象
        if isinstance(v, (dict, list)):
            return copy.deepcopy(v)
        return v

    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
        row = cursor.fetchone()
    if row:
        try:
            value = json.loads(row["value"])
        except (json.JSONDecodeError, ValueError):
            v = row["value"]
            if v in ("True", "true"):
                value = True
            elif v in ("False", "false"):
                value = False
            else:
                value = v
        # pydantic 校验（类型不匹配时返回默认值）
        try:
            from core.config_models import validate_config
            value = validate_config(key, value)
        except ImportError as e:
            silent_exc("db_config", e)
        # 写入缓存
        if len(_config_cache) >= _CONFIG_CACHE_MAX:
            # 清理过期条目
            expired = [k for k, (_, exp) in _config_cache.items() if exp <= now]
            for k in expired:
                del _config_cache[k]
            # 仍满则清最旧
            if len(_config_cache) >= _CONFIG_CACHE_MAX:
                oldest = min(_config_cache, key=lambda k: _config_cache[k][1])
                del _config_cache[oldest]
        # 深拷贝后存入缓存，防止调用方修改缓存中的可变对象
        if isinstance(value, (dict, list)):
            _config_cache[key] = (copy.deepcopy(value), now + _CONFIG_TTL)
        else:
            _config_cache[key] = (value, now + _CONFIG_TTL)
        return value
    return default


def set_config(key, value):
    from datetime import datetime
    with get_conn() as conn:
        cursor = conn.cursor()
        # 使用 JSON 保存所有类型，保持类型一致性
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, bool):
            value = json.dumps(value)
        elif isinstance(value, (int, float)):
            value = json.dumps(value)
        else:
            value = str(value)
        cursor.execute("INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?, ?, ?)", (key, value, datetime.now().isoformat()))
    # 失效缓存
    _config_cache.pop(key, None)