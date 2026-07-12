"""Utmaningslogik: värdeberäkning, leaderboard och nattliga snapshots.

Obs: leaderboarden läser medvetet över användargränser — deltagande i en
utmaning är opt-in-delning av just det mätetalet.
"""

import logging
import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import push
from app.models import (
    BodyMetric,
    CardioActivity,
    Challenge,
    ChallengeParticipant,
    ChallengeSnapshot,
    User,
    WorkoutSession,
)

logger = logging.getLogger(__name__)


def _period(challenge: Challenge) -> tuple[datetime, datetime]:
    start = datetime.combine(challenge.starts_on, time.min, tzinfo=timezone.utc)
    end = datetime.combine(
        challenge.ends_on + timedelta(days=1), time.min, tzinfo=timezone.utc
    )
    return start, end


async def _latest_metric_in_period(
    db: AsyncSession, user_id, metric: str, start: datetime, end: datetime
) -> float | None:
    row = await db.scalar(
        select(BodyMetric)
        .where(
            BodyMetric.user_id == user_id,
            BodyMetric.metric == metric,
            BodyMetric.measured_at >= start,
            BodyMetric.measured_at < end,
        )
        .order_by(BodyMetric.measured_at.desc())
        .limit(1)
    )
    return float(row.value) if row else None


async def participant_value(
    db: AsyncSession, challenge: Challenge, participant: ChallengeParticipant
) -> float:
    """Deltagarens nuvarande värde — högre är alltid bättre."""
    start, end = _period(challenge)
    uid = participant.user_id

    if challenge.metric == "workout_count":
        strength = await db.scalar(
            select(func.count(WorkoutSession.id)).where(
                WorkoutSession.user_id == uid,
                WorkoutSession.finished_at.is_not(None),
                WorkoutSession.started_at >= start,
                WorkoutSession.started_at < end,
            )
        )
        cardio = await db.scalar(
            select(func.count(CardioActivity.id)).where(
                CardioActivity.user_id == uid,
                CardioActivity.started_at >= start,
                CardioActivity.started_at < end,
            )
        )
        return float((strength or 0) + (cardio or 0))

    if challenge.metric == "distance_km":
        distance = await db.scalar(
            select(func.coalesce(func.sum(CardioActivity.distance_m), 0)).where(
                CardioActivity.user_id == uid,
                CardioActivity.started_at >= start,
                CardioActivity.started_at < end,
            )
        )
        return round(float(distance or 0) / 1000, 2)

    if challenge.metric == "weight_loss_kg":
        baseline = participant.baseline.get("weight")
        current = await _latest_metric_in_period(db, uid, "weight", start, end)
        if baseline is None or current is None:
            return 0.0
        return round(float(baseline) - current, 2)

    if challenge.metric == "fat_loss_percent":
        baseline = participant.baseline.get("fat_percent")
        current = await _latest_metric_in_period(db, uid, "fat_percent", start, end)
        if baseline is None or current is None:
            return 0.0
        return round(float(baseline) - current, 2)

    return 0.0


async def leaderboard(db: AsyncSession, challenge: Challenge) -> list[dict]:
    rows = []
    for participant in challenge.participants:
        user = await db.get(User, participant.user_id)
        value = await participant_value(db, challenge, participant)
        rows.append(
            {
                "user_id": str(participant.user_id),
                "name": (user.display_name or user.email.split("@")[0])
                if user
                else "?",
                "value": value,
                "baseline": participant.baseline,
            }
        )
    rows.sort(key=lambda r: r["value"], reverse=True)
    for i, row in enumerate(rows):
        row["rank"] = i + 1
    return rows


async def snapshot_baseline(db: AsyncSession, user_id, metric: str) -> dict:
    """Baseline som låses när en deltagare går med."""
    now = datetime.now(timezone.utc)
    horizon = now - timedelta(days=365 * 5)
    if metric == "weight_loss_kg":
        value = await _latest_metric_in_period(db, user_id, "weight", horizon, now)
        return {"weight": value} if value is not None else {}
    if metric == "fat_loss_percent":
        value = await _latest_metric_in_period(
            db, user_id, "fat_percent", horizon, now
        )
        return {"fat_percent": value} if value is not None else {}
    return {}


async def run_daily_snapshots(db: AsyncSession) -> dict:
    """Kör dagligen: spara dagens värden och pusha till omsprungna."""
    today = date.today()
    yesterday = today - timedelta(days=1)
    snapshots = 0
    notified = 0

    challenges = list(
        await db.scalars(
            select(Challenge).where(
                Challenge.starts_on <= today, Challenge.ends_on >= today
            )
        )
    )
    for challenge in challenges:
        board = await leaderboard(db, challenge)

        previous = {
            str(row.user_id): float(row.value)
            for row in await db.scalars(
                select(ChallengeSnapshot).where(
                    ChallengeSnapshot.challenge_id == challenge.id,
                    ChallengeSnapshot.day == yesterday,
                )
            )
        }
        prev_ranking = sorted(previous, key=lambda uid: previous[uid], reverse=True)
        prev_rank = {uid: i + 1 for i, uid in enumerate(prev_ranking)}

        for row in board:
            await db.merge(
                ChallengeSnapshot(
                    challenge_id=challenge.id,
                    user_id=uuid.UUID(row["user_id"]),
                    day=today,
                    value=row["value"],
                )
            )
            snapshots += 1

            old = prev_rank.get(row["user_id"])
            if old is not None and row["rank"] > old:
                # Någon gick om — hitta vem som ligger precis före nu
                ahead = next(
                    (r for r in board if r["rank"] == row["rank"] - 1), None
                )
                if ahead is not None:
                    notified += await push.send_to_user(
                        db,
                        uuid.UUID(row["user_id"]),
                        f"{ahead['name']} gick om dig! 🏃",
                        f"Du ligger nu {row['rank']}:a i \"{challenge.name}\" — "
                        "dags att svara!",
                        url="/social",
                    )
    await db.commit()
    return {"snapshots": snapshots, "notifications": notified}
