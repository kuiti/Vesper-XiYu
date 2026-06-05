from fastapi import APIRouter
from core.db import get_notes, add_note, delete_note
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/notes", tags=["notes"])

class NoteCreate(BaseModel):
    title: str
    content: str

class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None

class NoteOut(BaseModel):
    id: int
    title: str
    content: str
    created: str

@router.get("/", response_model=List[NoteOut])
async def list_notes():
    return get_notes()

@router.post("/")
async def create_note(note: NoteCreate):
    add_note(note.title, note.content)
    return {"status": "ok"}

@router.patch("/{note_id}")
async def update_note(note_id: int, note: NoteUpdate):
    from core.db import get_conn
    from fastapi import HTTPException
    with get_conn() as conn:
        c = conn.cursor()
        updates = {}
        if note.title is not None:
            updates["title"] = note.title
        if note.content is not None:
            updates["content"] = note.content
        if not updates:
            raise HTTPException(400, "没有需要更新的字段")
        sets = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [note_id]
        c.execute(f"UPDATE notes SET {sets} WHERE id = ?", vals)
        if c.rowcount == 0:
            raise HTTPException(404, "笔记不存在")
    return {"status": "ok"}

@router.delete("/{note_id}")
async def remove_note(note_id: int):
    from core.db import get_conn
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        if c.rowcount == 0:
            from fastapi import HTTPException
            raise HTTPException(404, "笔记不存在")
    return {"status": "ok"}