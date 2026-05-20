from fastapi import APIRouter
from core.db import get_notes, add_note, delete_note
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/notes", tags=["notes"])

class NoteCreate(BaseModel):
    title: str
    content: str

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

@router.delete("/{note_id}")
async def remove_note(note_id: int):
    delete_note(note_id)
    return {"status": "ok"}