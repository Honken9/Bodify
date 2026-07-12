from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
from app.db import get_session
from app.models import PushSubscription, User

router = APIRouter(prefix="/api/push", tags=["push"])


class SubscriptionIn(BaseModel):
    endpoint: str = Field(max_length=1024)
    keys: dict


@router.get("/vapid-public-key")
async def vapid_public_key() -> dict:
    key = get_settings().vapid_public_key
    if not key:
        raise HTTPException(503, "Push är inte konfigurerat (VAPID-nycklar saknas).")
    return {"key": key}


@router.post("/subscriptions", status_code=201)
async def subscribe(
    payload: SubscriptionIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    p256dh = payload.keys.get("p256dh")
    auth = payload.keys.get("auth")
    if not p256dh or not auth:
        raise HTTPException(400, "Prenumerationen saknar nycklar.")

    existing = await db.scalar(
        select(PushSubscription).where(
            PushSubscription.endpoint == payload.endpoint
        )
    )
    if existing is not None:
        existing.user_id = user.id
        existing.p256dh = p256dh
        existing.auth = auth
    else:
        db.add(
            PushSubscription(
                user_id=user.id,
                endpoint=payload.endpoint,
                p256dh=p256dh,
                auth=auth,
            )
        )
    await db.commit()
    return {"ok": True}


@router.delete("/subscriptions", status_code=204)
async def unsubscribe(
    payload: SubscriptionIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    sub = await db.scalar(
        select(PushSubscription).where(
            PushSubscription.endpoint == payload.endpoint,
            PushSubscription.user_id == user.id,
        )
    )
    if sub is not None:
        await db.delete(sub)
        await db.commit()
