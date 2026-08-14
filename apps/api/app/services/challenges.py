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
    MealEntry,
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

    if challenge.kind == "habit":
        completed, _total = await habit_weeks_completed(db, challenge, uid)
        return float(completed)

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

    return await value_between(db, challenge.metric, uid, start, end)


async def value_between(db: AsyncSession, metric_key, uid, start, end) -> float:
    """Värdet för ett mätetal i ett tidsfönster — delas av leaderboard
    (hela perioden) och etappberäkningen (en vecka i taget)."""
    if metric_key == "workout_count":
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

    if metric_key == "distance_km":
        distance = await db.scalar(
            select(func.coalesce(func.sum(CardioActivity.distance_m), 0)).where(
                CardioActivity.user_id == uid,
                CardioActivity.started_at >= start,
                CardioActivity.started_at < end,
            )
        )
        return round(float(distance or 0) / 1000, 2)

    if metric_key == "steps_total":
        # Bästa källan vinner per dag (samma logik som stegkortet) — summera
        rows = await db.execute(
            select(BodyMetric.measured_at, BodyMetric.value).where(
                BodyMetric.user_id == uid,
                BodyMetric.metric == "steps",
                BodyMetric.measured_at >= start,
                BodyMetric.measured_at < end,
            )
        )
        by_day: dict[str, float] = {}
        for measured_at, value in rows:
            key = measured_at.date().isoformat()
            by_day[key] = max(by_day.get(key, 0.0), float(value))
        return float(round(sum(by_day.values())))

    if metric_key in ("sleep_score_avg", "sleep_hours_avg"):
        metric = (
            "sleep_score" if metric_key == "sleep_score_avg" else "sleep_duration"
        )
        rows = list(
            await db.scalars(
                select(BodyMetric.value).where(
                    BodyMetric.user_id == uid,
                    BodyMetric.metric == metric,
                    BodyMetric.measured_at >= start,
                    BodyMetric.measured_at < end,
                )
            )
        )
        if not rows:
            return 0.0
        return round(sum(float(v) for v in rows) / len(rows), 2)

    if metric_key == "active_days":
        days: set = set()
        for row in await db.scalars(
            select(WorkoutSession.started_at).where(
                WorkoutSession.user_id == uid,
                WorkoutSession.finished_at.is_not(None),
                WorkoutSession.started_at >= start,
                WorkoutSession.started_at < end,
            )
        ):
            days.add(row.date())
        for row in await db.scalars(
            select(CardioActivity.started_at).where(
                CardioActivity.user_id == uid,
                CardioActivity.started_at >= start,
                CardioActivity.started_at < end,
            )
        ):
            days.add(row.date())
        return float(len(days))

    if metric_key == "workout_minutes":
        sessions = list(
            await db.scalars(
                select(WorkoutSession).where(
                    WorkoutSession.user_id == uid,
                    WorkoutSession.finished_at.is_not(None),
                    WorkoutSession.started_at >= start,
                    WorkoutSession.started_at < end,
                )
            )
        )
        strength_s = sum(
            max((s.finished_at - s.started_at).total_seconds(), 0)
            for s in sessions
        )
        cardio_s = await db.scalar(
            select(func.coalesce(func.sum(CardioActivity.duration_s), 0)).where(
                CardioActivity.user_id == uid,
                CardioActivity.started_at >= start,
                CardioActivity.started_at < end,
                CardioActivity.linked_session_id.is_(None),  # ej dubbelräkna
            )
        )
        return float(round((strength_s + float(cardio_s or 0)) / 60))

    if metric_key == "logged_days":
        count = await db.scalar(
            select(func.count(func.distinct(MealEntry.eaten_on))).where(
                MealEntry.user_id == uid,
                MealEntry.eaten_on >= start.date(),
                MealEntry.eaten_on < end.date(),
            )
        )
        return float(count or 0)

    return 0.0


async def habit_weeks_completed(
    db: AsyncSession, challenge: Challenge, user_id
) -> tuple[int, int]:
    """Vaneutmaning: (klarade veckor, totala veckor). Perioden delas i
    7-dagarsblock från startdatumet; ett block är klarat när antalet pass
    når målet (target.per_week)."""
    per_week = int((challenge.target or {}).get("per_week", 3))
    start, end = _period(challenge)
    stamps = [
        row
        for row in await db.scalars(
            select(WorkoutSession.started_at).where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.finished_at.is_not(None),
                WorkoutSession.started_at >= start,
                WorkoutSession.started_at < end,
            )
        )
    ]
    stamps += [
        row
        for row in await db.scalars(
            select(CardioActivity.started_at).where(
                CardioActivity.user_id == user_id,
                CardioActivity.started_at >= start,
                CardioActivity.started_at < end,
                CardioActivity.linked_session_id.is_(None),
            )
        )
    ]
    total_days = (challenge.ends_on - challenge.starts_on).days + 1
    total_weeks = max((total_days + 6) // 7, 1)
    per_block = [0] * total_weeks
    for stamp in stamps:
        block = (stamp.date() - challenge.starts_on).days // 7
        if 0 <= block < total_weeks:
            per_block[block] += 1
    completed = sum(1 for n in per_block if n >= per_week)
    return completed, total_weeks


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


async def history(db: AsyncSession, challenge: Challenge) -> dict:
    """Snapshot-serier för race-kurvorna: en linje per deltagare."""
    rows = list(
        await db.scalars(
            select(ChallengeSnapshot)
            .where(ChallengeSnapshot.challenge_id == challenge.id)
            .order_by(ChallengeSnapshot.day)
        )
    )
    days = sorted({r.day for r in rows})
    names: dict[str, str] = {}
    for p in challenge.participants:
        u = await db.get(User, p.user_id)
        names[str(p.user_id)] = (
            (u.display_name or u.email.split("@")[0]) if u else "?"
        )
    by_user: dict[str, dict[str, float]] = {}
    for r in rows:
        by_user.setdefault(str(r.user_id), {})[r.day.isoformat()] = float(r.value)
    series = []
    for uid, values in by_user.items():
        last = 0.0
        aligned = []
        for d in days:
            last = values.get(d.isoformat(), last)
            aligned.append(last)
        series.append({"user_id": uid, "name": names.get(uid, "?"), "values": aligned})
    return {"days": [d.isoformat() for d in days], "series": series}


# Mätetal där en veckoetapp är meningsfull (summor/snitt i fönster)
STAGEABLE_METRICS = {
    "steps_total",
    "workout_count",
    "distance_km",
    "workout_minutes",
    "active_days",
    "logged_days",
    "sleep_score_avg",
    "sleep_hours_avg",
}


async def stage_results(db: AsyncSession, challenge: Challenge) -> list[dict]:
    """Etapper: 7-dagarsblock i utmaningar ≥ 14 dagar — varje vecka har
    en egen vinnare så det alltid finns något att slåss om just nu."""
    duration = (challenge.ends_on - challenge.starts_on).days + 1
    if (
        duration < 14
        or challenge.kind == "habit"
        or challenge.metric not in STAGEABLE_METRICS
        or len(challenge.participants) < 2
    ):
        return []

    names = {}
    for p in challenge.participants:
        u = await db.get(User, p.user_id)
        names[p.user_id] = (
            (u.display_name or u.email.split("@")[0]) if u else "?"
        )

    today = date.today()
    stages = []
    stage_start = challenge.starts_on
    index = 0
    while stage_start <= challenge.ends_on and index < 12:
        index += 1
        stage_end = min(stage_start + timedelta(days=6), challenge.ends_on)
        entry = {
            "index": index,
            "start": stage_start.isoformat(),
            "end": stage_end.isoformat(),
            "completed": stage_end < today,
            "current": stage_start <= today <= stage_end,
            "winner": None,
            "value": None,
        }
        if stage_start <= today:
            start_dt = datetime.combine(
                stage_start, time.min, tzinfo=timezone.utc
            )
            end_dt = datetime.combine(
                stage_end + timedelta(days=1), time.min, tzinfo=timezone.utc
            )
            best = None
            for p in challenge.participants:
                value = await value_between(
                    db, challenge.metric, p.user_id, start_dt, end_dt
                )
                if best is None or value > best[1]:
                    best = (p.user_id, value)
            if best is not None and best[1] > 0:
                entry["winner"] = names.get(best[0], "?")
                entry["value"] = best[1]
        stages.append(entry)
        stage_start += timedelta(days=7)
    return stages


async def trophies(db: AsyncSession, user_id) -> list[dict]:
    """Avgjorda utmaningar användaren deltog i, med slutplacering."""
    today = date.today()
    rows = list(
        await db.scalars(
            select(Challenge)
            .join(
                ChallengeParticipant,
                ChallengeParticipant.challenge_id == Challenge.id,
            )
            .where(
                ChallengeParticipant.user_id == user_id,
                Challenge.ends_on < today,
            )
            .order_by(Challenge.ends_on.desc())
        )
    )
    result = []
    for challenge in rows:
        board = await leaderboard(db, challenge)
        mine = next(
            (r for r in board if r["user_id"] == str(user_id)), None
        )
        if mine is None:
            continue
        entry = {
            "challenge_id": str(challenge.id),
            "name": challenge.name,
            "metric": challenge.metric,
            "kind": challenge.kind,
            "ended_on": challenge.ends_on.isoformat(),
            "rank": mine["rank"],
            "value": mine["value"],
            "participants": len(board),
        }
        if challenge.kind == "habit":
            completed, total = await habit_weeks_completed(
                db, challenge, user_id
            )
            entry["habit_completed"] = completed == total
            entry["habit_weeks"] = f"{completed}/{total}"
        result.append(entry)
    return result


WEEKLY_TEMPLATES = [
    ("weekly_steps", "steps_total", "👟 Veckans stegkrig"),
    ("weekly_sleep", "sleep_score_avg", "😴 Sömnligan"),
]


async def ensure_weekly_challenges(db: AsyncSession) -> int:
    """Skapa veckans öppna standardutmaningar (må–sö) om de saknas.
    Körs av det nattliga jobbet — sajten får en puls utan arrangör."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    week = monday.isocalendar().week

    creator = await db.scalar(
        select(User).where(User.is_admin.is_(True)).order_by(User.created_at)
    )
    if creator is None:
        return 0

    created = 0
    for slug, metric, title in WEEKLY_TEMPLATES:
        name = f"{title} v.{week}"
        exists = await db.scalar(
            select(Challenge).where(
                Challenge.kind == "weekly",
                Challenge.metric == metric,
                Challenge.starts_on == monday,
            )
        )
        if exists is not None:
            continue
        db.add(
            Challenge(
                creator_id=creator.id,
                name=name,
                metric=metric,
                starts_on=monday,
                ends_on=sunday,
                is_open=True,
                kind="weekly",
            )
        )
        created += 1
    if created:
        await db.commit()
    return created


async def run_daily_snapshots(db: AsyncSession) -> dict:
    """Kör dagligen: veckoutmaningar, dagens värden, omsprungen-notiser,
    sista dagen-påminnelser och slutresultat."""
    today = date.today()
    yesterday = today - timedelta(days=1)
    snapshots = 0
    notified = 0

    weekly_created = await ensure_weekly_challenges(db)

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

        # Ledarbyte — dramat pushas till ALLA deltagare
        if len(board) > 1 and prev_ranking:
            old_leader = prev_ranking[0]
            new_leader = board[0]
            if new_leader["user_id"] != old_leader and new_leader["value"] > 0:
                for row in board:
                    if row["user_id"] == new_leader["user_id"]:
                        title, text = (
                            "🥇 Du tog ledningen!",
                            f"Du toppar nu \"{challenge.name}\" — försvara den!",
                        )
                    else:
                        title = f"🔥 {new_leader['name']} tog ledningen!"
                        text = f"Nytt läge i \"{challenge.name}\" — jaga!"
                    notified += await push.send_to_user(
                        db, uuid.UUID(row["user_id"]), title, text, url="/social"
                    )

        # Etappavgörande: i går var sista dagen på en veckoetapp
        days_in = (yesterday - challenge.starts_on).days
        if days_in >= 6 and days_in % 7 == 6:
            stages = await stage_results(db, challenge)
            stage_idx = days_in // 7  # 0-baserat → etappen som just avslutats
            if stage_idx < len(stages):
                stage = stages[stage_idx]
                if stage["completed"] and stage["winner"]:
                    for p in challenge.participants:
                        notified += await push.send_to_user(
                            db,
                            p.user_id,
                            f"🏁 Etapp {stage['index']} avgjord!",
                            f"{stage['winner']} tog veckan i "
                            f"\"{challenge.name}\" med {stage['value']:g}.",
                            url="/social",
                        )

        # Sista dagen — hinn påverka!
        if challenge.ends_on == today and len(board) > 1:
            for row in board:
                if row["rank"] == 1:
                    text = "Du leder — håll undan till målgången!"
                else:
                    ahead = next(
                        (r for r in board if r["rank"] == row["rank"] - 1), None
                    )
                    gap = round(ahead["value"] - row["value"], 1) if ahead else 0
                    text = (
                        f"Du ligger {row['rank']}:a, {gap:g} från "
                        f"{ahead['name']} — sista chansen!" if ahead else ""
                    )
                notified += await push.send_to_user(
                    db,
                    uuid.UUID(row["user_id"]),
                    f"🏁 Sista dagen i \"{challenge.name}\"",
                    text,
                    url="/social",
                )

    # Nyss avgjorda: skicka slutresultatet en gång (dagen efter målgång)
    finished = list(
        await db.scalars(
            select(Challenge).where(Challenge.ends_on == yesterday)
        )
    )
    for challenge in finished:
        board = await leaderboard(db, challenge)
        if not board:
            continue
        for row in board:
            if challenge.kind == "habit":
                completed, total = await habit_weeks_completed(
                    db, challenge, uuid.UUID(row["user_id"])
                )
                if completed == total:
                    title, text = (
                        f"🏆 Du klarade \"{challenge.name}\"!",
                        f"Alla {total} veckor i mål — grymt jobbat!",
                    )
                else:
                    title, text = (
                        f"\"{challenge.name}\" är slut",
                        f"Du klarade {completed} av {total} veckor — ny chans i nästa!",
                    )
            elif row["rank"] == 1:
                stake_line = (
                    f" Insatsen är din: {challenge.stake}."
                    if challenge.stake
                    else " Trofén finns på din profil."
                )
                title, text = (
                    f"🏆 Du vann \"{challenge.name}\"!",
                    f"Slutresultat: {row['value']:g}.{stake_line}",
                )
            else:
                medal = {2: "🥈", 3: "🥉"}.get(row["rank"], "🎖")
                title = f"{medal} \"{challenge.name}\" är avgjord"
                text = (
                    f"Du slutade {row['rank']}:a av {len(board)} med "
                    f"{row['value']:g}. Revansch?"
                )
            notified += await push.send_to_user(
                db, uuid.UUID(row["user_id"]), title, text, url="/social"
            )

    await db.commit()

    # Ligan: betygsätt nyavgjorda tävlingar (Elo + vinst-/comeback-märken)
    from app.services import badges as badge_service
    from app.services import league as league_service

    rating = await league_service.rate_finished_challenges(db)
    new_badges = await badge_service.evaluate_all(db)

    return {
        "snapshots": snapshots,
        "notifications": notified,
        "weekly_created": weekly_created,
        "rated": rating["rated"],
        "new_badges": new_badges,
    }
