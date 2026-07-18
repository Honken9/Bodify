"""Backfill av hela Strava-historiken till cardio_activities.

Webhooken fångar bara nya aktiviteter — den här hämtar allt bakåt i
tiden (paginerat, nyast först) så kartan och statistiken fylls från
dag ett. Idempotent: befintliga aktiviteter uppdateras på externt id.
"""

import logging
from datetime import timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations import strava
from app.models import CardioActivity, OAuthConnection

logger = logging.getLogger(__name__)

# Samma pass rapporteras ofta av både klockan (Withings) och Strava.
# Strava-versionen har GPS och rikast data — den vinner alltid.
DUP_WINDOW = timedelta(minutes=20)


async def remove_non_strava_duplicates(
    db: AsyncSession, user_id, activity_type: str, started_at
) -> int:
    """Ta bort Withings/Apple Health-kopior av ett Strava-pass (samma typ,
    start inom ±20 min). Manuellt loggade pass rörs aldrig."""
    dupes = list(
        await db.scalars(
            select(CardioActivity).where(
                CardioActivity.user_id == user_id,
                CardioActivity.source.in_(("withings", "apple_health")),
                CardioActivity.type == activity_type,
                CardioActivity.started_at >= started_at - DUP_WINDOW,
                CardioActivity.started_at <= started_at + DUP_WINDOW,
            )
        )
    )
    for dup in dupes:
        await db.delete(dup)
    return len(dupes)

MAX_PAGES = 100  # 100 × 200 = 20 000 aktiviteter — hela arkivet i praktiken


async def backfill_activities(
    conn: OAuthConnection, db: AsyncSession, max_pages: int = MAX_PAGES
) -> dict:
    imported = 0
    removed_dupes = 0
    paused = False
    for page in range(1, max_pages + 1):
        try:
            activities = await strava.fetch_activity_page(conn, db, page)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                # Stravas kvot (per 15 min) nådd — spara det vi fått;
                # nästa "Hämta historik" fortsätter där det tog slut.
                logger.warning("Strava-kvot nådd på sida %s — pausar.", page)
                paused = True
                break
            raise
        if not activities:
            break
        for activity in activities:
            fields = strava.normalize_activity(activity)
            removed_dupes += await remove_non_strava_duplicates(
                db, conn.user_id, fields["type"], fields["started_at"]
            )
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
    if removed_dupes:
        logger.info("Rensade %s klock-dubbletter av Strava-pass.", removed_dupes)

    # Slå ihop klockans gympass med Shapiqo-loggade styrkepass
    from app.models import User
    from app.services.watch_link import autolink_watch_activities

    user = await db.get(User, conn.user_id)
    if user is not None:
        await autolink_watch_activities(db, user)
    return {"imported": imported, "paused": paused}
