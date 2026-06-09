# core/character_card.py — 角色卡系统（兼容 SillyTavern V3 标准）
"""角色卡支持 V3 标准格式 + 佐仓扩展字段。
支持 JSON 导入导出、PNG 元数据嵌入/提取、多角色管理。

角色卡 V3 标准字段:
    spec, spec_version, name, description, personality, scenario,
    first_mes, mes_example, creator, tags, system_prompt, ...

佐仓扩展字段（放在 extensions.sakura 下）:
    foundation_type, foundation, taboos, tone, background, affection, trust
"""

from __future__ import annotations
import json
import os
import base64
import struct
import zlib
import hashlib
from datetime import datetime
from typing import Optional
from core.db import get_config, set_config, get_conn


# ─── PNG tEXt 块处理（纯 Python，无额外依赖）───

def _png_read_text_chunks(png_data: bytes) -> list[dict]:
    """读取 PNG 文件的所有 tEXt 块"""
    chunks = []
    pos = 8  # 跳过 PNG 签名
    while pos < len(png_data):
        length = struct.unpack('>I', png_data[pos:pos+4])[0]
        chunk_type = png_data[pos+4:pos+8].decode('latin-1')
        chunk_data = png_data[pos+8:pos+8+length]
        crc = struct.unpack('>I', png_data[pos+8+length:pos+12+length])[0]
        if chunk_type == 'tEXt':
            # tEXt 格式: keyword + null + text
            null_pos = chunk_data.find(b'\x00')
            if null_pos != -1:
                keyword = chunk_data[:null_pos].decode('latin-1')
                text = chunk_data[null_pos+1:].decode('latin-1')
                chunks.append({"keyword": keyword, "text": text})
        chunks.append({"type": chunk_type})
        pos += 12 + length
    return chunks


def _png_write_text_chunk(keyword: str, text: str) -> bytes:
    """生成一个 tEXt 块（用于嵌入到 PNG）"""
    data = keyword.encode('latin-1') + b'\x00' + text.encode('latin-1')
    chunk_type = b'tEXt'
    length = struct.pack('>I', len(data))
    crc_data = chunk_type + data
    crc = struct.pack('>I', zlib.crc32(crc_data) & 0xFFFFFFFF)
    return length + chunk_type + data + crc


def _png_replace_text_chunk(png_data: bytes, keyword: str, text: str) -> bytes:
    """替换 PNG 中的指定 tEXt 块，若无则追加到 IEND 前"""
    # 解析所有块
    chunks = []
    pos = 8
    while pos < len(png_data):
        length = struct.unpack('>I', png_data[pos:pos+4])[0]
        chunk_type = png_data[pos+4:pos+8]
        chunk_data = png_data[pos+8:pos+8+length]
        crc = struct.unpack('>I', png_data[pos+8+length:pos+12+length])[0]
        chunks.append({
            "length": length,
            "type": chunk_type,
            "data": chunk_data,
            "crc": crc,
            "raw": png_data[pos:pos+12+length]
        })
        pos += 12 + length

    # 分离 IHDR、其他块、IEND
    sig = png_data[:8]
    iend = chunks.pop() if chunks and chunks[-1]["type"] == b'IEND' else None
    if not iend:
        raise ValueError("无效 PNG：缺少 IEND 块")

    # 移除旧的同关键词 tEXt 块
    remaining = [c for c in chunks
                 if not (c["type"] == b'tEXt' and
                         c["data"].split(b'\x00')[0].decode('latin-1', errors='replace') == keyword)]

    # 生成新块
    new_chunk_raw = _png_write_text_chunk(keyword, text)

    # 重组
    result = sig
    for c in remaining:
        result += c["raw"]
    result += new_chunk_raw
    result += iend["raw"]
    return result


def _png_extract_text(png_data: bytes, keyword: str = "chara") -> str | None:
    """从 PNG 数据中提取指定关键词的 tEXt 文本"""
    pos = 8
    while pos < len(png_data):
        length = struct.unpack('>I', png_data[pos:pos+4])[0]
        chunk_type = png_data[pos+4:pos+8].decode('latin-1')
        chunk_data = png_data[pos+8:pos+8+length]
        if chunk_type == 'tEXt':
            null_pos = chunk_data.find(b'\x00')
            if null_pos != -1:
                kw = chunk_data[:null_pos].decode('latin-1')
                if kw.lower() == keyword.lower():
                    return chunk_data[null_pos+1:].decode('latin-1')
        pos += 12 + length
    return None


# ─── 角色卡类 ───

class CharacterCard:
    """角色卡，兼容 SillyTavern V3 标准 + 佐仓扩展"""

    def __init__(self, data: dict = None):
        self.data = data or self._default()
        self._ensure_spec()

    @staticmethod
    def _default() -> dict:
        return {
            "spec": "chara_card_v3",
            "spec_version": "3.0",
            "name": "佐仓",
            "description": "",
            "personality": "",
            "scenario": "",
            "first_mes": "",
            "mes_example": "",
            "creator": "",
            "creator_notes": "",
            "system_prompt": "",
            "post_history_instructions": "",
            "tags": [],
            "extensions": {
                "sakura": {
                    "foundation_type": "空白",
                    "foundation": "",
                    "taboos": [],
                    "tone": "冷静",
                    "background": {},
                    "affection": 30,
                    "trust": 30,
                    "created_at": "",
                }
            }
        }

    def _ensure_spec(self):
        """确保 V3 兼容字段存在"""
        if "spec" not in self.data:
            self.data["spec"] = "chara_card_v3"
            self.data["spec_version"] = "3.0"
        if "extensions" not in self.data:
            self.data["extensions"] = {}
        if "sakura" not in self.data.get("extensions", {}):
            self.data.setdefault("extensions", {})["sakura"] = {
                "foundation_type": "空白", "foundation": "",
                "taboos": [], "tone": "冷静", "background": {},
                "affection": 30, "trust": 30, "created_at": "",
            }

    # ─── 属性访问 ───

    @property
    def name(self) -> str:
        return self.data.get("name", "佐仓")

    @name.setter
    def name(self, v: str):
        self.data["name"] = v

    @property
    def sakura(self) -> dict:
        """佐仓扩展字段"""
        return self.data.setdefault("extensions", {}).setdefault("sakura", {})

    # ─── 导入/导出 ───

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.data, ensure_ascii=False, indent=indent)

    @classmethod
    def from_json(cls, text: str) -> "CharacterCard":
        data = json.loads(text)
        return cls(data)

    def to_png(self, avatar_path: str) -> bytes:
        """将角色卡嵌入到头像 PNG 中。返回新的 PNG 数据。"""
        with open(avatar_path, "rb") as f:
            png_data = f.read()
        # base64 编码 JSON 数据（SillyTavern 兼容）
        json_str = self.to_json(indent=None)
        b64_data = base64.b64encode(json_str.encode("utf-8")).decode("latin-1")
        # 同时写 V2 (chara) 和 V3 (ccv3) 块
        png_data = _png_replace_text_chunk(png_data, "chara", b64_data)
        png_data = _png_replace_text_chunk(png_data, "ccv3", b64_data)
        return png_data

    @classmethod
    def from_png(cls, png_path: str) -> "CharacterCard":
        """从 PNG 文件读取角色卡。先试 ccv3（V3），再试 chara（V2）。"""
        with open(png_path, "rb") as f:
            png_data = f.read()
        # V3 优先
        text = _png_extract_text(png_data, "ccv3")
        if text:
            b64_data = base64.b64decode(text.encode("latin-1")).decode("utf-8")
            return cls(json.loads(b64_data))
        # V2 回退
        text = _png_extract_text(png_data, "chara")
        if text:
            b64_data = base64.b64decode(text.encode("latin-1")).decode("utf-8")
            return cls(json.loads(b64_data))
        raise ValueError("PNG 文件中未找到角色卡数据")

    # ─── 佐仓当前配置双向同步 ───

    def sync_from_current(self):
        """从 DB config 读取当前设置，填充角色卡"""
        sakura = self.sakura
        self.data["name"] = get_config("ai_name", "佐仓")
        self.data["system_prompt"] = get_config("custom_system_prompt", "")
        sakura["tone"] = (get_config("personality", {}) or {}).get("tone", "冷静")
        sakura["foundation_type"] = self._get_bg_field("foundation_type", "空白")
        sakura["foundation"] = self._get_bg_field("foundation", "")
        sakura["taboos"] = self._get_bg_field("taboos", [])
        sakura["background"] = self._get_bg_field("legacy", {}) or self._get_bg_field("role", {})
        # 好感/信任
        try:
            from core.relationship import get_relationship
            affection, trust = get_relationship()
            sakura["affection"] = affection
            sakura["trust"] = trust
        except Exception:
            pass
        sakura["created_at"] = datetime.now().isoformat()

    def apply_to_current(self, card_name: str = None):
        """将角色卡数据应用到 DB config（保留完整角色卡名以备 prompt 注入）"""
        sakura = self.sakura
        set_config("ai_name", self.data.get("name", "佐仓"))
        set_config("custom_system_prompt", self.data.get("system_prompt", ""))
        # 记录当前激活的角色卡名（None 表示自定义/无卡片）
        if card_name:
            set_config("_active_character_card", card_name)
        # V3 额外字段存为 JSON，供 prompt 注入用
        extra_fields = json.dumps({
            "description": self.data.get("description", ""),
            "personality": self.data.get("personality", ""),
            "scenario": self.data.get("scenario", ""),
            "mes_example": self.data.get("mes_example", ""),
            "post_history_instructions": self.data.get("post_history_instructions", ""),
            "creator_notes": self.data.get("creator_notes", ""),
            "tags": self.data.get("tags", []),
            "taboos": sakura.get("taboos", []),
            "foundation": sakura.get("foundation", ""),
        }, ensure_ascii=False)
        set_config("_character_card_extra", extra_fields)
        # personality（只设 tone）
        personality = get_config("personality", {}) or {}
        if sakura.get("tone"):
            personality["tone"] = sakura["tone"]
        set_config("personality", personality)
        # background
        bg = json.loads(get_config("ai_background", "{}") or "{}")
        if sakura.get("foundation_type"):
            bg["foundation_type"] = sakura["foundation_type"]
        if sakura.get("foundation"):
            bg["foundation"] = sakura["foundation"]
        if sakura.get("taboos"):
            bg["taboos"] = sakura["taboos"]
        if sakura.get("background"):
            for k, v in sakura["background"].items():
                if isinstance(v, str) and v:
                    bg[k] = v
        set_config("ai_background", json.dumps(bg, ensure_ascii=False))
        # 好感/信任
        try:
            from core.relationship import set_relationship
            affection = sakura.get("affection", 30)
            trust = sakura.get("trust", 30)
            set_relationship(affection, trust)
        except Exception:
            pass

    def _get_bg_field(self, key: str, default=None):
        """从 ai_background JSON 中读取字段"""
        from core.persona_data import parse_ai_background
        bg = get_config("ai_background", "")
        obj = parse_ai_background(bg)
        return obj.get(key, default)

    # ─── 持久化 ───

    def save_to_db(self, card_name: str = None):
        """保存到 SQLite characters 表"""
        name = card_name or self.name
        now = datetime.now().isoformat()
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO characters (name, data, updated_at) VALUES (?, ?, ?)",
                (name, self.to_json(indent=None), now)
            )

    @classmethod
    def load_from_db(cls, card_name: str) -> Optional["CharacterCard"]:
        """从 SQLite characters 表加载"""
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data FROM characters WHERE name = ?", (card_name,))
            row = cursor.fetchone()
        if row:
            return cls(json.loads(row["data"]))
        return None

    @classmethod
    def list_all(cls) -> list[str]:
        """列出所有保存的角色卡名"""
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM characters ORDER BY updated_at DESC")
            return [r["name"] for r in cursor.fetchall()]

    @classmethod
    def delete(cls, card_name: str):
        """删除角色卡"""
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM characters WHERE name = ?", (card_name,))


# ─── Prompt 注入 ───

def get_active_card_prompt_block() -> str:
    """构建当前激活的角色卡的 prompt 注入块。
    返回空字符串表示无角色卡或字段为空。
    """
    card_name = get_config("_active_character_card", "")
    if not card_name:
        return ""
    extra_raw = get_config("_character_card_extra", "{}")
    try:
        extra = json.loads(extra_raw) if isinstance(extra_raw, str) else extra_raw
    except Exception:
        return ""

    parts = []
    if extra.get("description"):
        parts.append(f"【角色描述】{extra['description']}")
    if extra.get("personality"):
        parts.append(f"【性格】{extra['personality']}")
    if extra.get("scenario"):
        parts.append(f"【场景设定】{extra['scenario']}")
    taboos = extra.get("taboos", [])
    if taboos:
        parts.append(f"【禁忌话题】{'、'.join(taboos if isinstance(taboos, list) else [taboos])}")
    if extra.get("foundation"):
        parts.append(f"【关系基础】{extra['foundation']}")
    if extra.get("post_history_instructions"):
        parts.append(f"【回复指引】{extra['post_history_instructions']}")

    # mes_example 太长时只取头尾
    mes = extra.get("mes_example", "")
    if mes:
        lines = mes.strip().split("\n")
        if len(lines) > 12:
            mes = "\n".join(lines[:6]) + "\n……（中间省略）……\n" + "\n".join(lines[-4:])
        parts.append(f"【对话示例】\n{mes}")

    if not parts:
        return ""

    return f"\n——角色卡「{card_name}」设定——\n" + "\n".join(parts)
