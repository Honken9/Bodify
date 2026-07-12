"""ARQ-worker: bakgrundsjobb (synk, notiser, AI, nattliga aggregat).

Fas 0 innehåller bara ett heartbeat-jobb som visar att kedjan
Redis → worker → databas fungerar. Integrationsjobben läggs till i Fas 3.
"""

import logging

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import text

from app.config import get_settings
from app.db import SessionLocal
from app.services import challenges as challenge_service

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


class WorkerSettings:
    functions: list = []
    cron_jobs = [
        cron(heartbeat, minute=0),  # varje hel timme
        cron(challenge_snapshots, hour=20, minute=30),  # kvällssammanställning
    ]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
