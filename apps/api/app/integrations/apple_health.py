"""Apple Health-ingest via Health Auto Export (REST-automation).

Appen på iPhonen POST:ar JSON till /api/webhooks/apple-health med en
personlig Bearer-token. Payload-formatet är HAE:s standardexport:

  {"data": {"metrics": [{"name": "...", "units": "...",
                         "data": [{"date": "...", "qty": ...}]}],
            "workouts": [{"name": "Outdoor Run", "start": "...", ...}]}}
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BodyMetric, CardioActivity, SleepSession, User

logger = logging.getLogger(__name__)

# HAE-metriknamn → vårt metric-namn (+ ev. värdeskalning)
METRIC_MAP: dict[str, tuple[str, float]] = {
    "weight_body_mass": ("weight", 1.0),
    "body_fat_percentage": ("fat_percent", 1.0),
    "heart_rate_variability": ("hrv", 1.0),
    "resting_heart_rate": ("resting_hr", 1.0),
    "step_count": ("steps", 1.0),
    "vo2_max": ("vo2max", 1.0),
}

WORKOUT_TYPE_MAP = [
    ("run", "run"),
    ("löp", "run"),
    ("walk", "walk"),
    ("hike", "walk"),
    ("promenad", "walk"),
    ("cycl", "ride"),
    ("bike", "ride"),
    ("cykel", "ride"),
    ("swim", "swim"),
    ("sim", "swim"),
]


def _parse_date(value: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M %z"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _qty(value) -> float | None:
    if isinstance(value, dict):
        value = value.get("qty")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _workout_type(name: str) -> str:
    lowered = (name or "").lower()
    for needle, mapped in WORKOUT_TYPE_MAP:
        if needle in lowered:
            return mapped
    return "other"


async def ingest(user: User, payload: dict, db: AsyncSession) -> dict:
    """Normalisera in en HAE-export. Returnerar räknare per datatyp."""
    data = payload.get("data") or {}
    counts = {"metrics": 0, "sleep": 0, "workouts": 0, "skipped": 0}

    for metric_block in data.get("metrics") or []:
        name = metric_block.get("name")

        if name == "sleep_analysis":
            counts["sleep"] += await _ingest_sleep(user, metric_block, db)
            continue

        mapped = METRIC_MAP.get(name)
        if mapped is None:
            counts["skipped"] += 1
            continue
        metric, scale = mapped
        for point in metric_block.get("data") or []:
            measured_at = _parse_date(point.get("date") or "")
            value = _qty(point)
            if measured_at is None or value is None:
                continue
            await db.merge(
                BodyMetric(
                    user_id=user.id,
                    metric=metric,
                    measured_at=measured_at,
                    source="apple_health",
                    value=round(value * scale, 3),
                )
            )
            counts["metrics"] += 1

    for workout in data.get("workouts") or []:
        counts["workouts"] += await _ingest_workout(user, workout, db)

    await db.commit()
    return counts


async def _ingest_sleep(user: User, block: dict, db: AsyncSession) -> int:
    added = 0
    for point in block.get("data") or []:
        start = _parse_date(point.get("sleepStart") or point.get("startDate") or "")
        end = _parse_date(point.get("sleepEnd") or point.get("endDate") or "")
        if start is None or end is None:
            continue

        def hours_to_s(key: str) -> int:
            v = _qty(point.get(key))
            return int((v or 0) * 3600)

        existing = await db.scalar(
            select(SleepSession).where(
                SleepSession.user_id == user.id,
                SleepSession.start_at == start,
                SleepSession.source == "apple_health",
            )
        )
        if existing is not None:
            continue
        db.add(
            SleepSession(
                user_id=user.id,
                start_at=start,
                end_at=end,
                deep_s=hours_to_s("deep"),
                rem_s=hours_to_s("rem"),
                light_s=hours_to_s("core") or hours_to_s("asleep"),
                awake_s=hours_to_s("awake"),
                source="apple_health",
            )
        )
        added += 1
    return added


async def _ingest_workout(user: User, workout: dict, db: AsyncSession) -> int:
    start = _parse_date(workout.get("start") or "")
    end = _parse_date(workout.get("end") or "")
    if start is None or end is None:
        return 0

    workout_type = _workout_type(workout.get("name") or "")

    # Dedupe: samma pass kommer ofta även via Strava — hoppa över om en
    # aktivitet av samma typ startar inom ±15 minuter.
    window = timedelta(minutes=15)
    overlap = await db.scalar(
        select(CardioActivity).where(
            CardioActivity.user_id == user.id,
            CardioActivity.type == workout_type,
            CardioActivity.started_at >= start - window,
            CardioActivity.started_at <= start + window,
        )
    )
    if overlap is not None:
        return 0

    duration_s = int((end - start).total_seconds())
    distance = _qty(workout.get("distance"))
    distance_m = None
    if distance is not None:
        units = (
            workout.get("distance", {}).get("units", "km")
            if isinstance(workout.get("distance"), dict)
            else "km"
        )
        distance_m = distance * 1000 if units == "km" else distance
    pace = (
        round(duration_s / (distance_m / 1000), 1)
        if distance_m and distance_m > 100
        else None
    )

    external_id = workout.get("id") or f"hae-{start.timestamp():.0f}"
    existing = await db.scalar(
        select(CardioActivity).where(
            CardioActivity.user_id == user.id,
            CardioActivity.source == "apple_health",
            CardioActivity.external_id == str(external_id),
        )
    )
    if existing is not None:
        return 0

    db.add(
        CardioActivity(
            user_id=user.id,
            type=workout_type,
            source="apple_health",
            external_id=str(external_id),
            name=(workout.get("name") or "")[:200] or None,
            started_at=start,
            duration_s=duration_s,
            distance_m=distance_m,
            avg_hr=_qty(workout.get("avgHeartRate")),
            max_hr=_qty(workout.get("maxHeartRate")),
            avg_pace_s_per_km=pace,
            calories=_qty(workout.get("activeEnergyBurned")),
        )
    )
    return 1
