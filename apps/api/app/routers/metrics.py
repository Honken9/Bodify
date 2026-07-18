from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_session
from app.models import METRICS, BodyMetric, User

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


class MetricPoint(BaseModel):
    measured_at: datetime
    value: float
    source: str


class ManualMetric(BaseModel):
    metric: str
    value: float = Field(ge=0, le=100000)
    measured_at: datetime | None = None


@router.get("/latest")
async def latest_metrics(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    rows = list(
        await db.scalars(
            select(BodyMetric)
            .where(BodyMetric.user_id == user.id)
            .order_by(BodyMetric.measured_at.asc())
        )
    )
    latest: dict[str, dict] = {}
    for row in rows:  # sorterat stigande → sista vinner
        latest[row.metric] = {
            "value": float(row.value),
            "measured_at": row.measured_at.isoformat(),
            "source": row.source,
        }
    return latest


@router.get("/{metric}", response_model=list[MetricPoint])
async def metric_series(
    metric: str,
    days: int = 90,
    start: date | None = None,
    end: date | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[BodyMetric]:
    """Serie för ett mätetal. Antingen `days` bakåt från nu, eller ett
    exakt fönster med `start`/`end` (båda inklusive) — används av
    dag/vecko/månadsvyerna som bläddrar ett steg i taget."""
    if metric not in METRICS:
        raise HTTPException(404, "Okänt mätetal.")
    if start is not None and end is not None:
        since = datetime.combine(start, time.min, tzinfo=timezone.utc)
        until = datetime.combine(
            end + timedelta(days=1), time.min, tzinfo=timezone.utc
        )
    else:
        since = datetime.now(timezone.utc) - timedelta(
            days=min(max(days, 1), 3660)
        )
        until = datetime.now(timezone.utc) + timedelta(days=1)
    rows = await db.scalars(
        select(BodyMetric)
        .where(
            BodyMetric.user_id == user.id,
            BodyMetric.metric == metric,
            BodyMetric.measured_at >= since,
            BodyMetric.measured_at < until,
        )
        .order_by(BodyMetric.measured_at)
    )
    return list(rows)


@router.post("", status_code=201)
async def add_manual_metric(
    payload: ManualMetric,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    if payload.metric not in METRICS:
        raise HTTPException(400, "Okänt mätetal.")
    measured_at = payload.measured_at or datetime.now(timezone.utc)
    await db.merge(
        BodyMetric(
            user_id=user.id,
            metric=payload.metric,
            measured_at=measured_at,
            source="manual",
            value=payload.value,
        )
    )
    await db.commit()
    return {"ok": True}
