"""Backfill av hela Strava-historiken till cardio_activities.

Webhooken fångar bara nya aktiviteter — den här hämtar allt bakåt i
tiden (paginerat, nyast först) så kartan och statistiken fylls från
dag ett. Idempotent: befintliga aktiviteter uppdateras på externt id.
"""

import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations import strava
from app.models import CardioActivity, OAuthConnection

logger = logging.getLogger(__name__)

MAX_PAGES = 100  # 100 × 200 = 20 000 aktiviteter — hela arkivet i praktiken


async def backfill_activities(
    conn: OAuthConnection, db: AsyncSession, max_pages: int = MAX_PAGES
) -> int:
    imported = 0
    for page in range(1, max_pages + 1):
        try:
            activities = await strava.fetch_activity_page(conn, db, page)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                # Stravas kvot (per 15 min) nådd — spara det vi fått;
                # nästa "Hämta historik" fortsätter där det tog slut.
                logger.warning("Strava-kvot nådd på sida %s — pausar.", page)
                break
            raise
        if not activities:
            break
        for activity in activities:
            fields = strava.normalize_activity(activity)
            existing = await db.scalar(
                select(CardioActivity).where(
                    CardioActivity.user_id == conn.user_id,
                    CardioActivity.source == "strava",
                    CardioActivity.external_id == fields["external_id"],
                )
            )
            if existing is not None:
                for key, value in fields.items():
                    setattr(existing, key, value)
            else:
                db.add(
                    CardioActivity(
                        user_id=conn.user_id, source="strava", **fields
                    )
                )
                imported += 1
        await db.commit()
        if len(activities) < 200:
            break  # sista sidan
    return imported
