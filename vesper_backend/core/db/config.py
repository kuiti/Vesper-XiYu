# core/db/config.py  |  config 表 CRUD
"""配置表 CRUD 模块：带 TTL 缓存的配置读写，支持 JSON 类型自动序列化。"""

import json
import copy
import time as _time
import threading
from . import get_conn
from core.retry import silent_exc

# 影响 LLM provider 缓存的配置键
_provider_config_keys = frozenset({"llm_provider", "api_base_url", "api_model", "api_key", "api_provider"})

# ========== 配置缓存 ==========
_config_cache = {}
_config_cache_lock = threading.Lock()  # {key: (value, expire_ts)}
_CONFIG_TTL = 30.0  # 30 秒缓存，平衡响应速度与 DB 压力
_CONFIG_CACHE_MAX = 500


def clear_config_cache():
    """清除整个配置缓存（重置等批量操作后调用）"""
    _config_cache.clear()


def get_config(key, default=None):
    """读取配置项，优先走缓存，支持 JSON 类型自动解析和 pydantic 校验。"""
    with _config_cache_lock:
        now = _time.time()
        cached = _config_cache.get(key)
        if cached and cached[1] > now:
            v = cached[0]
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
    """写入配置项，自动序列化为 JSON 字符串并清除缓存。"""
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
    if key in _provider_config_keys:
        try:
            from core.llm_provider import clear_provider_cache
            clear_provider_cache()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[config] 清除 provider 缓存失败: {e}")
    _config_cache.pop(key, None)


def get_char_config(key: str, character_id: int = 0, default=None):
    """读取角色私有配置（per-character config 表）。
    与 get_config 共享缓存逻辑，但用 character_id/key 复合键隔离。
    """
    from . import get_chat_conn
    cache_key = f"char_{character_id}_{key}"
    with _config_cache_lock:
        now = _time.time()
        cached = _config_cache.get(cache_key)
        if cached and cached[1] > now:
            v = cached[0]
            if isinstance(v, (dict, list)):
                return copy.deepcopy(v)
            return v

    with get_chat_conn(character_id) as conn:
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
        # 缓存写入
        if len(_config_cache) >= _CONFIG_CACHE_MAX:
            expired = [k for k, (_, exp) in _config_cache.items() if exp <= now]
            for k in expired:
                del _config_cache[k]
            if len(_config_cache) >= _CONFIG_CACHE_MAX:
                oldest = min(_config_cache, key=lambda k: _config_cache[k][1])
                del _config_cache[oldest]
        if isinstance(value, (dict, list)):
            _config_cache[cache_key] = (copy.deepcopy(value), now + _CONFIG_TTL)
        else:
            _config_cache[cache_key] = (value, now + _CONFIG_TTL)
        return value
    return default


def set_char_config(key: str, value, character_id: int = 0):
    """写入角色私有配置（per-character config 表）。"""
    from datetime import datetime
    from . import get_chat_conn
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    elif isinstance(value, bool):
        value = json.dumps(value)
    elif isinstance(value, (int, float)):
        value = json.dumps(value)
    else:
        value = str(value)
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?, ?, ?)",
                       (key, value, datetime.now().isoformat()))
    cache_key = f"char_{character_id}_{key}"
    _config_cache.pop(cache_key, None)


def resolve_config(key: str, default=None, character_id: int = 0):
    """三级配置查询链：角色私有配置 → 全局配置 → 默认值。

    用于需要在角色级别覆盖全局设置的场景（如 api_key、api_provider）。
    """
    if character_id:
        val = get_char_config(key, character_id)
        if val is not None:
            return val
    val = get_config(key)
    return val if val is not None else default