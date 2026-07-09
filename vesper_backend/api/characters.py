# api/characters.py — 角色卡管理 API
"""角色卡的 CRUD、导入导出（JSON/PNG）、切换当前角色"""

import json
import os
import tempfile
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import Response, JSONResponse
from core.character_card import CharacterCard
import logging
from core.retry import silent_exc
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/characters", tags=["characters"])


@router.get("/")
async def list_characters():
    """列出所有已保存的角色卡"""
    char_list = CharacterCard.list_all()
    cards = []
    for entry in char_list:
        cid = entry.get("id", 0) if isinstance(entry, dict) else entry
        card = CharacterCard.load_from_db(cid)
        if card:
            settings = card.data.get("settings", {}) or {}
            if isinstance(settings, str):
                try:
                    import json
                    settings = json.loads(settings)
                except Exception:
                    settings = {}
            tone = settings.get("tone") or card.data.get("personality", {}).get("tone", "冷静")
            cards.append({
                "name": card.name,
                "description": card.data.get("description", "")[:80],
                "tags": card.data.get("tags", []),
                "tone": tone,
            })
    return {"characters": cards}


@router.get("/current")
async def get_current_character():
    """获取当前应用的角色卡（从 DB config 构建）"""
    card = CharacterCard()
    card.sync_from_current()
    return {"character": card.data}


@router.post("/current/save")
async def save_current_character():
    """将当前配置保存为角色卡"""
    card = CharacterCard()
    card.sync_from_current()
    card.save_to_db()
    return {"status": "ok", "name": card.name}


@router.post("/current/apply")
async def apply_character(data: dict):
    """应用指定角色卡到当前配置"""
    name = data.get("name", "")
    if not name:
        raise HTTPException(400, "缺少 name 参数")
    card = CharacterCard.load_from_db(name)
    if not card:
        raise HTTPException(404, f"角色卡 '{name}' 不存在")
    card.apply_to_current(card_name=name)
    # 清除 provider 缓存 + prompt 缓存
    try:
        from core.llm_provider import clear_provider_cache
        clear_provider_cache()
    except Exception as e:
        silent_exc("apply_character", e)
    from core.prompt_builder import clear_persona_cache
    clear_persona_cache()
    return {"status": "ok", "name": name}


@router.post("/import/json")
async def import_json(data: dict):
    """导入 JSON 格式角色卡"""
    # 基本数据校验
    if not isinstance(data, dict):
        raise HTTPException(400, "数据必须是 JSON 对象")
    # 检查必要字段
    required_fields = ["name", "description"]
    for field in required_fields:
        if field not in data:
            raise HTTPException(400, f"缺少必要字段: {field}")
    # 限制字段数量，防止注入过多配置
    allowed_fields = {"name", "description", "personality", "scenario", "first_mes",
                      "mes_example", "system_prompt", "tags", "spec", "spec_version",
                      "data", "metadata", "extensions"}
    extra_fields = set(data.keys()) - allowed_fields
    if extra_fields:
        # 移除不允许的字段
        for field in extra_fields:
            del data[field]
    try:
        card = CharacterCard.from_json(json.dumps(data))
    except Exception as e:
        raise HTTPException(400, f"角色卡格式错误: {e}")
    card.save_to_db()
    return {"status": "ok", "name": card.name}


@router.post("/import/png")
async def import_png(file: UploadFile = File(...)):
    """从 PNG 文件导入角色卡（SillyTavern 兼容）"""
    if not file.filename or not file.filename.lower().endswith(".png"):
        raise HTTPException(400, "请上传 PNG 文件")
    try:
        content = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        card = CharacterCard.from_png(tmp_path)
        os.unlink(tmp_path)
    except Exception as e:
        raise HTTPException(400, f"角色卡解析失败: {e}")
    card.save_to_db()
    return {"status": "ok", "name": card.name, "card": card.data}


@router.get("/export/{name}/json")
async def export_json(name: str):
    """导出角色卡为 JSON"""
    card = CharacterCard.load_from_db(name)
    if not card:
        raise HTTPException(404, f"角色卡 '{name}' 不存在")
    return JSONResponse(content=card.data)


@router.get("/export/{name}/png")
async def export_png(name: str):
    """导出角色卡为 PNG（需有头像文件）"""
    card = CharacterCard.load_from_db(name)
    if not card:
        raise HTTPException(404, f"角色卡 '{name}' 不存在")

    # 查找当前头像
    avatar_path = "data/avatars/avatar.png"
    if not os.path.exists(avatar_path):
        # 用 data/avatars/ 下第一个 PNG
        avatars = [f for f in os.listdir("data/avatars") if f.lower().endswith(".png")]
        if avatars:
            avatar_path = os.path.join("data/avatars", sorted(avatars)[0])
        else:
            raise HTTPException(400, "未找到头像文件，请先设置头像")

    try:
        png_data = card.to_png(avatar_path)
    except Exception as e:
        raise HTTPException(500, f"生成角色卡 PNG 失败: {e}")

    return Response(
        content=png_data,
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{name}.png"'},
    )


@router.delete("/{name}")
async def delete_character(name: str):
    """删除角色卡"""
    CharacterCard.delete(name)
    return {"status": "ok"}
