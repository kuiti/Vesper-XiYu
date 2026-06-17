# core/user_persona.py — 用户身份系统
"""独立于角色卡的用户身份管理。

用法:
    from core.user_persona import user_persona_manager
    personas = user_persona_manager.list_personas()
    user_persona_manager.set_active("student")
"""

from __future__ import annotations
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional
from core.db import get_conn, get_config, set_config


@dataclass
class UserPersona:
    id: int = 0
    name: str = ""
    description: str = ""
    avatar: str = ""
    is_default: bool = False
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "UserPersona":
        return cls(
            id=d.get("id", 0),
            name=d.get("name", ""),
            description=d.get("description", ""),
            avatar=d.get("avatar", ""),
            is_default=bool(d.get("is_default", False)),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
        )


class UserPersonaManager:
    def __init__(self):
        self._personas: list[UserPersona] = []
        self._dirty = True
        self._ensure_table()

    def _ensure_table(self):
        with get_conn() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS user_personas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                avatar TEXT NOT NULL DEFAULT '',
                is_default INTEGER NOT NULL DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )""")

    def _load_all(self):
        if not self._dirty:
            return
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM user_personas ORDER BY is_default DESC, id ASC"
            ).fetchall()
        self._personas = [UserPersona.from_dict(dict(r)) for r in rows]
        self._dirty = False

    def _mark_dirty(self):
        self._dirty = True

    def list_personas(self) -> list[dict]:
        self._load_all()
        return [asdict(p) for p in self._personas]

    def get_persona(self, persona_id: int) -> Optional[dict]:
        self._load_all()
        for p in self._personas:
            if p.id == persona_id:
                return asdict(p)
        return None

    def add_persona(self, name: str, description: str = "",
                    avatar: str = "", is_default: bool = False) -> int:
        now = datetime.now().isoformat()
        with get_conn() as conn:
            if is_default:
                conn.execute("UPDATE user_personas SET is_default=0")
            cursor = conn.execute(
                "INSERT INTO user_personas (name, description, avatar, is_default, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (name, description, avatar, int(is_default), now, now),
            )
            persona_id = cursor.lastrowid
        self._mark_dirty()
        return persona_id

    def update_persona(self, persona_id: int, **kwargs) -> bool:
        allowed = {"name", "description", "avatar", "is_default"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        now = datetime.now().isoformat()
        updates["updated_at"] = now
        with get_conn() as conn:
            if updates.get("is_default"):
                conn.execute("UPDATE user_personas SET is_default=0")
            set_clause = ", ".join(f"{k}=?" for k in updates)
            values = list(updates.values()) + [persona_id]
            conn.execute(f"UPDATE user_personas SET {set_clause} WHERE id=?", values)
        self._mark_dirty()
        return True

    def delete_persona(self, persona_id: int) -> bool:
        with get_conn() as conn:
            conn.execute("DELETE FROM user_personas WHERE id=?", (persona_id,))
        self._mark_dirty()
        # 如果删除的是当前活跃身份，重置
        active_id = get_config("_active_user_persona", "")
        if str(persona_id) == str(active_id):
            set_config("_active_user_persona", "")
        return True

    def get_active_persona(self) -> Optional[dict]:
        """获取当前活跃的用户身份。优先 _active_user_persona，其次 is_default，最后 None。"""
        active_id = get_config("_active_user_persona", "")
        if active_id:
            try:
                p = self.get_persona(int(active_id))
                if p:
                    return p
            except (ValueError, TypeError):
                pass
        # Fallback to default
        self._load_all()
        for p in self._personas:
            if p.is_default:
                return asdict(p)
        return None

    def set_active(self, persona_id: int) -> bool:
        """设置当前活跃的身份"""
        if not self.get_persona(persona_id):
            return False
        set_config("_active_user_persona", str(persona_id))
        return True

    def get_active_description(self) -> str:
        """获取当前活跃身份的描叙，用于 prompt 注入"""
        p = self.get_active_persona()
        if p and p.get("description"):
            return p["description"]
        return ""


user_persona_manager = UserPersonaManager()
