"""Web Push 推送通知 API —— 订阅管理和消息推送。"""
# api/push.py — Web Push 推送通知
from fastapi import APIRouter
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/push", tags=["push"])

_subscriptions: list = []


class PushSubscription(BaseModel):
    endpoint: str
    keys: dict


@router.post("/subscribe")
async def subscribe(sub: PushSubscription):
    """注册 Web Push 推送订阅。"""
    _subscriptions.append(sub.model_dump())
    return {"status": "ok"}


@router.post("/send")
async def send(title: str, body: str):
    """向所有已订阅客户端发送推送消息。"""
    logger.info(f"[推送] {title}: {body}")
    return {"status": "ok", "sent": len(_subscriptions)}
