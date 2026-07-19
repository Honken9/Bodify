"""ARQ-worker: bakgrundsjobb — utmaningssnapshots, veckorapporter och
smarta påminnelser. Cron-tiderna är i UTC (svensk tid = UTC+1/+2)."""

import logging
from datetime import date, datetime, time, timedelta, timezone

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import func, select, text

from app import push
from app.config import get_settings
from app.db import SessionLocal
from app.models import MealEntry, User, WorkoutSession
from app.services import challenges as challenge_service
from app.services import weekly_report as report_service

logger = logging.getLogger(__name__)


async def heartbeat(ctx: dict) -> str:
    async with SessionLocal() as session:
        await session.execute(text("SELECT 1"))
    logger.info("Worker-heartbeat: databasen svarar.")
    return "ok"


async def challenge_snapshots(ctx: dict) -> dict:
    """Nattligt: spara dagens utmaningsvärden + pusha till omsprungna."""
    async with SessionLocal() as session:
        result = await challenge_service.run_daily_snapshots(session)
    logger.info("Utmanings-snapshots: %s", result)
    return result


async def weekly_reports(ctx: dict) -> dict:
    """Måndagsmorgon: pusha veckorapporten till alla användare."""
    sent = 0
    async with SessionLocal() as session:
        users = list(await session.scalars(select(User)))
        for user in users:
            report = await report_service.weekly_report(session, user.id)
            c = report["current"]
            if not any(
                [c["strength_sessions"], c["cardio_sessions"], c["steps"]]
            ):
                continue  # tom vecka — stör inte
            sent += await push.send_to_user(
                session,
                user.id,
                f"📊 Din veckorapport (v.{report['week']})",
                report_service.summary_text(report),
                url="/",
            )
    logger.info("Veckorapporter skickade: %s", sent)
    return {"sent": sent}


async def meal_reminders(ctx: dict) -> dict:
    """Kväll: påminn den som brukar logga kost men inte gjort det idag."""
    today = date.today()
    week_ago = today - timedelta(days=7)
    sent = 0
    async with SessionLocal() as session:
        users = list(await session.scalars(select(User)))
        for user in users:
            logged_today = await session.scalar(
                select(func.count(MealEntry.id)).where(
                    MealEntry.user_id == user.id,
                    MealEntry.eaten_on == today,
                )
            )
            if logged_today:
                continue
            # Bara den som faktiskt använder kostloggen (≥3 dgr sista veckan)
            recent_days = await session.scalar(
                select(func.count(func.distinct(MealEntry.eaten_on))).where(
                    MealEntry.user_id == user.id,
                    MealEntry.eaten_on >= week_ago,
                    MealEntry.eaten_on < today,
                )
            )
            if (recent_days or 0) < 3:
                continue
            sent += await push.send_to_user(
                session,
                user.id,
                "🥗 Glöm inte maten",
                "Inget loggat idag ännu — fota middagen eller skanna in den "
                "så håller du din svit vid liv!",
                url="/food",
            )
    logger.info("Kostpåminnelser: %s", sent)
    return {"sent": sent}


async def workout_reminders(ctx: dict) -> dict:
    """Eftermiddag: 'du brukar träna den här veckodagen' — vaneväckning."""
    now = datetime.now(timezone.utc)
    today = date.today()
    weekday = today.weekday()
    sent = 0
    async with SessionLocal() as session:
        users = list(await session.scalars(select(User)))
        for user in users:
            trained_today = await session.scalar(
                select(func.count(WorkoutSession.id)).where(
                    WorkoutSession.user_id == user.id,
                    WorkoutSession.started_at
                    >= datetime.combine(today, time.min, tzinfo=timezone.utc),
                )
            )
            if trained_today:
                continue
            # Minst 2 av senaste 4 samma veckodagar hade ett avslutat pass?
            hits = 0
            for weeks_back in range(1, 5):
                day = today - timedelta(days=7 * weeks_back)
                start = datetime.combine(day, time.min, tzinfo=timezone.utc)
                count = await session.scalar(
                    select(func.count(WorkoutSession.id)).where(
                        WorkoutSession.user_id == user.id,
                        WorkoutSession.finished_at.is_not(None),
                        WorkoutSession.started_at >= start,
                        WorkoutSession.started_at < start + timedelta(days=1),
                    )
                )
                if count:
                    hits += 1
            if hits < 2:
                continue
            day_name = [
                "måndagar", "tisdagar", "onsdagar", "torsdagar",
                "fredagar", "lördagar", "söndagar",
            ][weekday]
            sent += await push.send_to_user(
                session,
                user.id,
                "🏋️ Dags att träna?",
                f"Du brukar köra på {day_name} — passet väntar!",
                url="/programs",
            )
    logger.info("Träningspåminnelser: %s (utskick %s)", sent, now.isoformat())
    return {"sent": sent}


class WorkerSettings:
    functions: list = []
    cron_jobs = [
        cron(heartbeat, minute=0),  # varje hel timme
        cron(challenge_snapshots, hour=20, minute=30),  # kvällssammanställning
        cron(weekly_reports, weekday=0, hour=6, minute=0),  # måndag ~08 svensk tid
        cron(meal_reminders, hour=18, minute=0),  # ~20 svensk sommartid
        cron(workout_reminders, hour=15, minute=0),  # ~17 svensk sommartid
    ]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
