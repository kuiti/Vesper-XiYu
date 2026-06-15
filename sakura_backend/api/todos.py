from fastapi import APIRouter, HTTPException
from core.db import get_todos, add_todo
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
    from core.db import get_conn
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        if c.rowcount == 0:
            raise HTTPException(404, "待办不存在")
    return {"status": "ok"}