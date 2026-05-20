from fastapi import APIRouter, HTTPException
from core.db import get_todos, add_todo, toggle_todo, delete_todo
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/todos", tags=["todos"])

class TodoCreate(BaseModel):
    task: str

class TodoUpdate(BaseModel):
    done: bool

class TodoOut(BaseModel):
    id: int
    task: str
    done: bool
    created: str

@router.get("/", response_model=List[TodoOut])
async def list_todos():
    return get_todos()

@router.post("/")
async def create_todo(todo: TodoCreate):
    add_todo(todo.task)
    return {"status": "ok"}

@router.patch("/{todo_id}")
async def update_todo(todo_id: int, update: TodoUpdate):
    from core.db import set_todo_done
    set_todo_done(todo_id, update.done)
    return {"status": "ok"}

@router.delete("/{todo_id}")
async def remove_todo(todo_id: int):
    delete_todo(todo_id)
    return {"status": "ok"}