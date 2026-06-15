from fastapi import APIRouter
from core.db import get_countdowns, add_countdown
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/countdowns", tags=["countdowns"])

class CountdownCreate(BaseModel):
    name: str
    target_date: str

class CountdownUpdate(BaseModel):
    name: Optional[str] = None
    target_date: Optional[str] = None

class CountdownOut(BaseModel):
    id: int
    name: str
    target: str

@router.get("/", response_model=List[CountdownOut])
async def list_countdowns():
    return get_countdowns()

@router.post("/")
async def create_countdown(cd: CountdownCreate):
    add_countdown(cd.name, cd.target_date)
    return {"status": "ok"}

@router.patch("/{cd_id}")
async def update_countdown(cd_id: int, cd: CountdownUpdate):
    from core.db import get_conn
    from fastapi import HTTPException
    with get_conn() as conn:
        c = conn.cursor()
        updates = {}
        if cd.name is not None:
            updates["name"] = cd.name
        if cd.target_date is not None:
            updates["target_date"] = cd.target_date
        if not updates:
            raise HTTPException(400, "没有需要更新的字段")
        sets = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [cd_id]
        c.execute(f"UPDATE countdowns SET {sets} WHERE id = ?", vals)
        if c.rowcount == 0:
            raise HTTPException(404, "倒计时不存在")
    return {"status": "ok"}

@router.delete("/{cd_id}")
async def remove_countdown(cd_id: int):
    from core.db import get_conn
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM countdowns WHERE id = ?", (cd_id,))
        if c.rowcount == 0:
            from fastapi import HTTPException
            raise HTTPException(404, "倒计时不存在")
    return {"status": "ok"}
