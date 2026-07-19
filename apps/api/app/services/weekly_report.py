"""Veckorapporten: senast avslutade veckans facit, jämfört med veckan
innan. Visas som hemkort och pushas ut på måndagsmorgonen."""

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    BodyMetric,
    CardioActivity,
    MealEntry,
    WorkoutSession,
)


async def _week_stats(db: AsyncSession, user_id, monday: date) -> dict:
    start = datetime.combine(monday, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=7)
    sunday = monday + timedelta(days=6)

    strength = await db.scalar(
        select(func.count(WorkoutSession.id)).where(
            WorkoutSession.user_id == user_id,
            WorkoutSession.finished_at.is_not(None),
            WorkoutSession.started_at >= start,
            WorkoutSession.started_at < end,
        )
    )
    cardio_rows = await db.execute(
        select(
            func.count(CardioActivity.id),
            func.coalesce(func.sum(CardioActivity.distance_m), 0),
            func.coalesce(func.sum(CardioActivity.duration_s), 0),
        ).where(
            CardioActivity.user_id == user_id,
            CardioActivity.started_at >= start,
            CardioActivity.started_at < end,
            CardioActivity.linked_session_id.is_(None),
        )
    )
    cardio_count, cardio_m, cardio_s = cardio_rows.one()

    # Steg: bästa källan per dag, summerat
    steps_by_day: dict[str, float] = {}
    for measured_at, value in await db.execute(
        select(BodyMetric.measured_at, BodyMetric.value).where(
            BodyMetric.user_id == user_id,
            BodyMetric.metric == "steps",
            BodyMetric.measured_at >= start,
            BodyMetric.measured_at < end,
        )
    ):
        key = measured_at.date().isoformat()
        steps_by_day[key] = max(steps_by_day.get(key, 0.0), float(value))

    async def _avg(metric: str) -> float | None:
        rows = [
            float(v)
            for v in await db.scalars(
                select(BodyMetric.value).where(
                    BodyMetric.user_id == user_id,
                    BodyMetric.metric == metric,
                    BodyMetric.measured_at >= start,
                    BodyMetric.measured_at < end,
                )
            )
        ]
        return round(sum(rows) / len(rows), 1) if rows else None

    weights = [
        float(v)
        for v in await db.scalars(
            select(BodyMetric.value)
            .where(
                BodyMetric.user_id == user_id,
                BodyMetric.metric == "weight",
                BodyMetric.measured_at >= start,
                BodyMetric.measured_at < end,
            )
            .order_by(BodyMetric.measured_at)
        )
    ]

    meal_rows = (
        await db.execute(
            select(MealEntry.eaten_on, func.sum(MealEntry.kcal))
            .where(
                MealEntry.user_id == user_id,
                MealEntry.eaten_on >= monday,
                MealEntry.eaten_on <= sunday,
            )
            .group_by(MealEntry.eaten_on)
        )
    ).all()

    return {
        "strength_sessions": int(strength or 0),
        "cardio_sessions": int(cardio_count or 0),
        "cardio_km": round(float(cardio_m or 0) / 1000, 1),
        "workout_minutes": round(float(cardio_s or 0) / 60),
        "steps": round(sum(steps_by_day.values())),
        "sleep_hours_avg": await _avg("sleep_duration"),
        "sleep_score_avg": await _avg("sleep_score"),
        "weight_last": weights[-1] if weights else None,
        "weight_delta": (
            round(weights[-1] - weights[0], 1) if len(weights) >= 2 else None
        ),
        "kcal_avg": (
            round(sum(float(r[1]) for r in meal_rows) / len(meal_rows))
            if meal_rows
            else None
        ),
        "logged_days": len(meal_rows),
    }


async def weekly_report(db: AsyncSession, user_id) -> dict:
    """Rapport för senast AVSLUTADE veckan + jämförelse med veckan innan."""
    today = date.today()
    this_monday = today - timedelta(days=today.weekday())
    monday = this_monday - timedelta(days=7)
    current = await _week_stats(db, user_id, monday)
    previous = await _week_stats(db, user_id, monday - timedelta(days=7))
    return {
        "week": monday.isocalendar().week,
        "monday": monday.isoformat(),
        "sunday": (monday + timedelta(days=6)).isoformat(),
        "current": current,
        "previous": previous,
    }


def summary_text(report: dict) -> str:
    """Kort pushtext: veckans viktigaste siffror."""
    c = report["current"]
    parts = []
    total_pass = c["strength_sessions"] + c["cardio_sessions"]
    if total_pass:
        parts.append(f"{total_pass} pass")
    if c["steps"]:
        parts.append(f"{c['steps']:,} steg".replace(",", " "))
    if c["sleep_hours_avg"]:
        parts.append(f"sömn {c['sleep_hours_avg']} h/natt")
    if c["weight_delta"] is not None:
        parts.append(f"vikt {c['weight_delta']:+g} kg")
    return " · ".join(parts) if parts else "En lugn vecka — ny chans nu!"
