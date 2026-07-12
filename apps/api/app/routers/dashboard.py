from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_session
from app.models import (
    BodyMetric,
    CardioActivity,
    MealEntry,
    User,
    WorkoutSession,
    WorkoutSet,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

PERIODS = {"week": 7, "month": 30, "year": 365}


@router.get("")
async def dashboard(
    period: str = "week",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    days = PERIODS.get(period, 7)
    since_dt = datetime.now(timezone.utc) - timedelta(days=days)
    since_d = date.today() - timedelta(days=days - 1)

    strength_count = await db.scalar(
        select(func.count(WorkoutSession.id)).where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.finished_at.is_not(None),
            WorkoutSession.started_at >= since_dt,
        )
    )
    volume = await db.scalar(
        select(func.coalesce(func.sum(WorkoutSet.weight_kg * WorkoutSet.reps), 0))
        .join(WorkoutSession, WorkoutSession.id == WorkoutSet.session_id)
        .where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.started_at >= since_dt,
            WorkoutSet.is_warmup.is_(False),
        )
    )
    cardio_rows = await db.execute(
        select(
            func.count(CardioActivity.id),
            func.coalesce(func.sum(CardioActivity.distance_m), 0),
        ).where(
            CardioActivity.user_id == user.id,
            CardioActivity.started_at >= since_dt,
        )
    )
    cardio_count, cardio_distance = cardio_rows.one()

    # Kost: snitt per dag som har loggning
    meal_rows = await db.execute(
        select(
            MealEntry.eaten_on,
            func.sum(MealEntry.kcal),
            func.sum(MealEntry.protein_g),
        )
        .where(MealEntry.user_id == user.id, MealEntry.eaten_on >= since_d)
        .group_by(MealEntry.eaten_on)
    )
    meal_days = meal_rows.all()
    avg_kcal = (
        round(sum(float(r[1]) for r in meal_days) / len(meal_days))
        if meal_days
        else None
    )
    avg_protein = (
        round(sum(float(r[2]) for r in meal_days) / len(meal_days))
        if meal_days
        else None
    )

    # Viktförändring under perioden
    weight_rows = list(
        await db.scalars(
            select(BodyMetric)
            .where(
                BodyMetric.user_id == user.id,
                BodyMetric.metric == "weight",
                BodyMetric.measured_at >= since_dt,
            )
            .order_by(BodyMetric.measured_at)
        )
    )
    weight_delta = (
        round(float(weight_rows[-1].value) - float(weight_rows[0].value), 1)
        if len(weight_rows) >= 2
        else None
    )

    # Aktivitet per dag (för stapeldiagram/streak)
    strength_days = {
        row[0]
        for row in await db.execute(
            select(func.date(WorkoutSession.started_at)).where(
                WorkoutSession.user_id == user.id,
                WorkoutSession.finished_at.is_not(None),
                WorkoutSession.started_at >= since_dt,
            )
        )
    }
    cardio_days = {
        row[0]
        for row in await db.execute(
            select(func.date(CardioActivity.started_at)).where(
                CardioActivity.user_id == user.id,
                CardioActivity.started_at >= since_dt,
            )
        )
    }

    def _as_date(value) -> date:
        return value if isinstance(value, date) else date.fromisoformat(str(value))

    strength_set = {_as_date(d) for d in strength_days}
    cardio_set = {_as_date(d) for d in cardio_days}

    day_list = [since_d + timedelta(days=i) for i in range(days)]
    activity = [
        {
            "day": d.isoformat(),
            "strength": d in strength_set,
            "cardio": d in cardio_set,
        }
        for d in day_list
    ]

    return {
        "period": period,
        "strength_sessions": strength_count or 0,
        "total_volume_kg": round(float(volume or 0)),
        "cardio_sessions": cardio_count or 0,
        "cardio_distance_km": round(float(cardio_distance or 0) / 1000, 1),
        "avg_kcal": avg_kcal,
        "avg_protein_g": avg_protein,
        "logged_days": len(meal_days),
        "weight_delta_kg": weight_delta,
        "active_days": len(strength_set | cardio_set),
        "activity": activity if days <= 31 else [],
    }
