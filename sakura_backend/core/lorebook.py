# core/lorebook.py — 知识库系统（SillyTavern World Info 方案）
"""关键词触发的知识条目，匹配后注入 prompt。

用法:
    from core.lorebook import lorebook_manager

    # 匹配当前用户消息
    entries = lorebook_manager.match_entries("我们去公园散步吧")
    # → ["关于公园的知识..."]

    # 管理条目
    lorebook_manager.add_entry(keys=["公园"], content="Yuki小时候常去的公园...")
"""

from __future__ import annotations
import json
import re
import random
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional
from core.db import get_conn


# ─── 数据类 ───

@dataclass
class LorebookEntry:
    id: int = 0
    keys: list = field(default_factory=list)       # 触发关键词
    content: str = ""                               # 注入内容
    priority: int = 5                               # 优先级（高→低）
    position: str = "after_persona"                 # before_persona / after_persona / depth:N
    logic: str = "AND_ANY"                          # AND_ANY / AND_ALL / REGEX
    group_name: str = ""                            # 互斥组（同组只取priority最高的）
    probability: int = 100                          # 触发概率 0-100
    sticky: int = 0                                 # 触发后持续 N 轮
    cooldown: int = 0                               # 冷却 N 轮
    scope: str = "global"                           # global / character / chat
    character_name: str = ""                        # scope=character 时有效
    enabled: bool = True
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "LorebookEntry":
        d = {k: v for k, v in d.items() if k in LorebookEntry.__dataclass_fields__}
        if isinstance(d.get("keys"), str):
            try:
                d["keys"] = json.loads(d["keys"])
            except (json.JSONDecodeError, TypeError):
                d["keys"] = [d["keys"]]
        d.setdefault("enabled", True)
        return cls(**d)


# ─── 管理器 ───

class LorebookManager:
    """知识库管理器（带缓存）。"""

    def __init__(self):
        self._entries: list[LorebookEntry] = []
        self._dirty = True
        self._timed: dict[str, dict] = {}     # {entry_key: {"sticky_until": int, "cooldown_until": int}}
        self._msg_counter = 0
        self._ensure_table()
        self._migrate_old_registry()

    # ─── 建表 ───

    def _ensure_table(self):
        with get_conn() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS lorebook (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keys TEXT NOT NULL DEFAULT '[]',
                content TEXT NOT NULL DEFAULT '',
                priority INTEGER NOT NULL DEFAULT 5,
                position TEXT NOT NULL DEFAULT 'after_persona',
                logic TEXT NOT NULL DEFAULT 'AND_ANY',
                group_name TEXT NOT NULL DEFAULT '',
                probability INTEGER NOT NULL DEFAULT 100,
                sticky INTEGER NOT NULL DEFAULT 0,
                cooldown INTEGER NOT NULL DEFAULT 0,
                scope TEXT NOT NULL DEFAULT 'global',
                character_name TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_lorebook_scope ON lorebook(scope, enabled)")

    # ─── 旧注册表迁移（一次性）────

    def _migrate_old_registry(self):
        from core.db import get_config
        if get_config("_lorebook_migrated", ""):
            return
        # 迁移旧的三条硬编码知识条目
        old_entries = [
            {
                "keys": ["生日", "birthday"],
                "content": "用户提到生日时，注意记录日期，并在临近时主动提醒。生日是重要的情感节点。",
                "priority": 8,
            },
            {
                "keys": ["考试", "面试", "exam", "interview"],
                "content": "用户提到考试或面试时，这是高压力事件。给予支持和鼓励，不要施加额外压力。",
                "priority": 7,
            },
            {
                "keys": ["难过", "伤心", "委屈", "哭"],
                "content": "用户情绪低落时，先接住情绪（'嗯，我听到了'），不要急于给建议。陪伴比解决方案更重要。",
                "priority": 9,
            },
        ]
        for e in old_entries:
            self.add_entry(**e)
        from core.db import set_config
        set_config("_lorebook_migrated", "true")

    # ─── 缓存 ───

    def _load_all(self):
        if not self._dirty:
            return
        with get_conn() as conn:
            rows = conn.execute("SELECT * FROM lorebook ORDER BY priority DESC").fetchall()
        self._entries = [LorebookEntry.from_dict(dict(r)) for r in rows]
        self._dirty = False

    def _mark_dirty(self):
        self._dirty = True

    # ─── CRUD ───

    def add_entry(self, keys: list[str] = None, content: str = "", priority: int = 5,
                  position: str = "after_persona", logic: str = "AND_ANY",
                  group_name: str = "", probability: int = 100,
                  sticky: int = 0, cooldown: int = 0,
                  scope: str = "global", character_name: str = "",
                  enabled: bool = True) -> int:
        now = datetime.now().isoformat()
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO lorebook (keys, content, priority, position, logic,
                   group_name, probability, sticky, cooldown, scope, character_name,
                   enabled, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (json.dumps(keys or [], ensure_ascii=False), content, priority, position,
                 logic, group_name, probability, sticky, cooldown,
                 scope, character_name, int(enabled), now, now)
            )
            entry_id = cursor.lastrowid
        self._mark_dirty()
        return entry_id

    def update_entry(self, entry_id: int, **kwargs) -> bool:
        allowed = {"keys", "content", "priority", "position", "logic", "group_name",
                   "probability", "sticky", "cooldown", "scope", "character_name", "enabled"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        now = datetime.now().isoformat()
        updates["updated_at"] = now
        if "keys" in updates and isinstance(updates["keys"], list):
            updates["keys"] = json.dumps(updates["keys"], ensure_ascii=False)
        if "enabled" in updates:
            updates["enabled"] = int(updates["enabled"])
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [entry_id]
        with get_conn() as conn:
            conn.execute(f"UPDATE lorebook SET {set_clause} WHERE id=?", values)
        self._mark_dirty()
        return True

    def delete_entry(self, entry_id: int) -> bool:
        with get_conn() as conn:
            conn.execute("DELETE FROM lorebook WHERE id=?", (entry_id,))
        self._mark_dirty()
        return True

    def list_entries(self, scope: str = None) -> list[dict]:
        self._load_all()
        entries = self._entries
        if scope:
            entries = [e for e in entries if e.scope == scope]
        result = []
        for e in entries:
            d = asdict(e)
            if isinstance(d.get("keys"), str):
                try:
                    d["keys"] = json.loads(d["keys"])
                except (json.JSONDecodeError, TypeError):
                    d["keys"] = []
            result.append(d)
        return result

    def get_entry(self, entry_id: int) -> Optional[dict]:
        self._load_all()
        for e in self._entries:
            if e.id == entry_id:
                d = asdict(e)
                if isinstance(d.get("keys"), str):
                    try:
                        d["keys"] = json.loads(d["keys"])
                    except (json.JSONDecodeError, TypeError):
                        d["keys"] = []
                return d
        return None

    # ─── 匹配 ───

    def match_entries(self, user_message: str, scope: str = "global",
                      max_chars: int = 1200) -> list[dict]:
        """根据用户消息匹配知识条目。返回 [(content, position, priority), ...]。"""
        if not user_message:
            return []
        self._load_all()
        self._msg_counter += 1
        msg_lower = user_message.lower()

        matched = []
        for entry in self._entries:
            if not entry.enabled:
                continue
            if entry.scope != "global" and entry.scope != scope:
                continue

            entry_key = "|".join(entry.keys) + f"|{entry.id}"
            timed = self._timed.get(entry_key, {})

            # 冷却检查
            if timed.get("cooldown_until", 0) > self._msg_counter:
                continue

            # 粘性激活（即使关键词不匹配也注入）
            is_sticky = timed.get("sticky_until", 0) > self._msg_counter
            if is_sticky:
                matched.append(entry)
                continue

            # 关键词匹配
            is_match = False
            if entry.logic == "REGEX":
                try:
                    for key in entry.keys:
                        if len(key) > 200:
                            continue
                        if re.search(key, msg_lower, re.TIMEOUT if hasattr(re, 'TIMEOUT') else 0):
                            is_match = True
                            break
                except re.error:
                    pass
                except Exception:
                    pass
            elif entry.logic == "AND_ALL":
                is_match = all(key in msg_lower for key in entry.keys)
            elif entry.logic == "NOT_ANY":
                is_match = not any(key in msg_lower for key in entry.keys)
            elif entry.logic == "NOT_ALL":
                is_match = not all(key in msg_lower for key in entry.keys)
            else:  # AND_ANY (default)
                is_match = any(key in msg_lower for key in entry.keys)

            if not is_match:
                continue

            # 概率过滤
            if entry.probability < 100 and random.randint(1, 100) > entry.probability:
                continue

            matched.append(entry)

            # 更新计时
            new_timed = {}
            if entry.sticky > 0:
                new_timed["sticky_until"] = self._msg_counter + entry.sticky
            if entry.cooldown > 0:
                new_timed["cooldown_until"] = self._msg_counter + entry.cooldown
            if new_timed:
                self._timed[entry_key] = {**timed, **new_timed}

        # 组互斥：同组只保留 priority 最高的
        if matched:
            groups = {}
            for entry in matched:
                if entry.group_name:
                    if entry.group_name not in groups or entry.priority > groups[entry.group_name].priority:
                        groups[entry.group_name] = entry
            matched = [e for e in matched if not e.group_name or
                       (e.group_name in groups and e.id == groups[e.group_name].id)]

        # 按优先级排序，截断字符预算
        matched.sort(key=lambda x: -x.priority)
        result = []
        total = 0
        for entry in matched:
            if total + len(entry.content) > max_chars:
                remain = max_chars - total
                if remain > 100:
                    result.append({
                        "content": entry.content[:remain] + "...",
                        "position": entry.position,
                        "priority": entry.priority,
                    })
                break
            result.append({
                "content": entry.content,
                "position": entry.position,
                "priority": entry.priority,
            })
            total += len(entry.content)

        return result


# ─── 全局单例 ───

lorebook_manager = LorebookManager()
