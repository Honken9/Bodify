import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_session
from app.models import CardioActivity, User

router = APIRouter(prefix="/api/cardio", tags=["cardio"])


class CardioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    source: str
    name: str | None
    started_at: datetime
    duration_s: int
    distance_m: float | None
    avg_hr: float | None
    max_hr: float | None
    avg_pace_s_per_km: float | None
    calories: float | None


class CardioCreate(BaseModel):
    type: str = Field(pattern="^(run|ride|walk|swim|other)$")
    name: str | None = Field(default=None, max_length=200)
    started_at: datetime
    duration_s: int = Field(gt=0, le=86400)
    distance_m: float | None = Field(default=None, gt=0, le=1_000_000)
    avg_hr: float | None = Field(default=None, gt=0, le=250)


@router.get("", response_model=list[CardioOut])
async def list_activities(
    limit: int = 30,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[CardioActivity]:
    rows = await db.scalars(
        select(CardioActivity)
        .where(CardioActivity.user_id == user.id)
        .order_by(CardioActivity.started_at.desc())
        .limit(min(limit, 100))
        .offset(offset)
    )
    return list(rows)


@router.post("", response_model=CardioOut, status_code=201)
async def add_activity(
    payload: CardioCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> CardioActivity:
    pace = (
        round(payload.duration_s / (payload.distance_m / 1000), 1)
        if payload.distance_m and payload.distance_m > 100
        else None
    )
    activity = CardioActivity(
        user_id=user.id,
        source="manual",
        external_id=None,
        type=payload.type,
        name=payload.name,
        started_at=payload.started_at,
        duration_s=payload.duration_s,
        distance_m=payload.distance_m,
        avg_hr=payload.avg_hr,
        avg_pace_s_per_km=pace,
    )
    db.add(activity)
    await db.commit()
    await db.refresh(activity)
    return activity


@router.delete("/{activity_id}", status_code=204)
async def delete_activity(
    activity_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    activity = await db.get(CardioActivity, activity_id)
    if activity is None or activity.user_id != user.id:
        raise HTTPException(404, "Aktiviteten finns inte.")
    await db.delete(activity)
    await db.commit()
