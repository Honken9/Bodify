"""Readiness-motor: deterministiska regler för återhämtning.

Besluten fattas av regelmotor (testbar, förklarbar) — LLM:en används bara
för att formulera rådet i klartext. Signaler:

- HRV-trend:       7-dagarssnitt vs 28-dagarssnitt (lägre = sämre)
- Vilopuls-trend:  7-dagarssnitt vs 28-dagarssnitt (högre = sämre)
- Sömn i natt:     timmar vs eget 7-dagarssnitt
- Belastning:      akut:kronisk träningskvot (ACWR), pass senaste 7 dagarna
                   vs veckosnitt senaste 28 dagarna
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BodyMetric, CardioActivity, SleepSession, WorkoutSession

GREEN, YELLOW, RED = "green", "yellow", "red"
_ORDER = {GREEN: 0, YELLOW: 1, RED: 2}


async def _metric_avg(
    db: AsyncSession, user_id: uuid.UUID, metric: str, days: int, offset_days: int = 0
) -> float | None:
    end = datetime.now(timezone.utc) - timedelta(days=offset_days)
    start = end - timedelta(days=days)
    value = await db.scalar(
        select(func.avg(BodyMetric.value)).where(
            BodyMetric.user_id == user_id,
            BodyMetric.metric == metric,
            BodyMetric.measured_at >= start,
            BodyMetric.measured_at < end,
        )
    )
    return float(value) if value is not None else None


async def _session_count(
    db: AsyncSession, user_id: uuid.UUID, days: int
) -> int:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    strength = await db.scalar(
        select(func.count(WorkoutSession.id)).where(
            WorkoutSession.user_id == user_id,
            WorkoutSession.finished_at.is_not(None),
            WorkoutSession.started_at >= since,
        )
    )
    cardio = await db.scalar(
        select(func.count(CardioActivity.id)).where(
            CardioActivity.user_id == user_id,
            CardioActivity.started_at >= since,
        )
    )
    return (strength or 0) + (cardio or 0)


async def compute_readiness(db: AsyncSession, user_id: uuid.UUID) -> dict:
    factors: list[dict] = []

    # HRV-trend
    hrv_7 = await _metric_avg(db, user_id, "hrv", 7)
    hrv_28 = await _metric_avg(db, user_id, "hrv", 28)
    if hrv_7 is not None and hrv_28:
        ratio = hrv_7 / hrv_28
        status = RED if ratio < 0.85 else YELLOW if ratio < 0.93 else GREEN
        factors.append(
            {
                "name": "HRV",
                "status": status,
                "detail": f"7-dagarssnitt {hrv_7:.0f} ms vs {hrv_28:.0f} ms "
                f"({(ratio - 1) * 100:+.0f} %)",
            }
        )

    # Vilopuls-trend
    rhr_7 = await _metric_avg(db, user_id, "resting_hr", 7)
    rhr_28 = await _metric_avg(db, user_id, "resting_hr", 28)
    if rhr_7 is not None and rhr_28:
        ratio = rhr_7 / rhr_28
        status = RED if ratio > 1.08 else YELLOW if ratio > 1.04 else GREEN
        factors.append(
            {
                "name": "Vilopuls",
                "status": status,
                "detail": f"7-dagarssnitt {rhr_7:.0f} vs {rhr_28:.0f} bpm "
                f"({(ratio - 1) * 100:+.0f} %)",
            }
        )

    # Sömn i natt
    since = datetime.now(timezone.utc) - timedelta(hours=30)
    last_sleep = await db.scalar(
        select(SleepSession)
        .where(SleepSession.user_id == user_id, SleepSession.end_at >= since)
        .order_by(SleepSession.end_at.desc())
        .limit(1)
    )
    if last_sleep is not None:
        hours = (last_sleep.end_at - last_sleep.start_at).total_seconds() / 3600
        awake_h = last_sleep.awake_s / 3600
        slept = max(hours - awake_h, 0)
        status = RED if slept < 5.5 else YELLOW if slept < 6.5 else GREEN
        factors.append(
            {
                "name": "Sömn",
                "status": status,
                "detail": f"{slept:.1f} h i natt",
            }
        )

    # Träningsbelastning (ACWR-approximation på passfrekvens)
    acute = await _session_count(db, user_id, 7)
    total_28 = await _session_count(db, user_id, 28)
    chronic_weekly = total_28 / 4 if total_28 else 0
    if chronic_weekly >= 1:
        acwr = acute / chronic_weekly
        status = RED if acwr > 1.6 else YELLOW if acwr > 1.3 else GREEN
        factors.append(
            {
                "name": "Belastning",
                "status": status,
                "detail": f"{acute} pass senaste veckan vs "
                f"{chronic_weekly:.1f}/vecka i snitt (kvot {acwr:.2f})",
            }
        )

    if not factors:
        return {
            "status": "unknown",
            "factors": [],
            "recommendation": "Ingen återhämtningsdata ännu — koppla Apple "
            "Health (sömn/HRV) under Kopplingar så vaknar coachen till liv.",
        }

    overall = max((f["status"] for f in factors), key=lambda s: _ORDER[s])
    recommendation = {
        GREEN: "Grönt ljus — kör dagens pass som planerat! 💪",
        YELLOW: "Lite sliten? Kör dagens pass men dra ner vikterna ~10 % "
        "eller korta passet.",
        RED: "Kroppen skriker på vila — ta en vilodag eller ersätt passet "
        "med promenad/rörlighet.",
    }[overall]

    return {"status": overall, "factors": factors, "recommendation": recommendation}
