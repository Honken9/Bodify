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

logger = logging.getLogger(__name__)


async def heartbeat(ctx: dict) -> str:
    async with SessionLocal() as session:
        await session.execute(text("SELECT 1"))
    logger.info("Worker-heartbeat: databasen svarar.")
    return "ok"


class WorkerSettings:
    functions: list = []
    cron_jobs = [cron(heartbeat, minute=0)]  # varje hel timme
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
