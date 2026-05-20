from fastapi import APIRouter
from core.db import get_countdowns, add_countdown, delete_countdown
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/countdowns", tags=["countdowns"])

class CountdownCreate(BaseModel):
    name: str
    target_date: str

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

@router.delete("/{cd_id}")
async def remove_countdown(cd_id: int):
    delete_countdown(cd_id)
    return {"status": "ok"}
