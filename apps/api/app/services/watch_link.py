"""Ihopslagning av klockpass och Shapiqo-loggade styrkepass.

Samma gympass registreras ofta två gånger: set för set i Shapiqo och
som "styrketräning" på klockan (via Withings/Strava/Apple Health).
Här länkas klockans version till det loggade passet när starttiderna
ligger nära varandra — klockans puls/kalorier berikar styrkepasset och
kopian räknas inte som ett eget pass i statistik och listor.

Användaren styr: profilflaggan auto_merge_watch stänger av helt, och
en isärkopplad länk (autolink_opt_out) återskapas aldrig av synkarna.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CardioActivity, User, WorkoutSession

# Klockan startas sällan exakt samtidigt som passet loggas i appen
LINK_WINDOW = timedelta(minutes=90)

WATCH_SOURCES = ("withings", "strava", "apple_health")


def auto_merge_enabled(user: User) -> bool:
    return (user.profile or {}).get("auto_merge_watch", True) is not False


def _utc(dt: datetime) -> datetime:
    """SQLite ger naiva tidsstämplar, Postgres medvetna — jämför i UTC."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


async def autolink_watch_activities(db: AsyncSession, user: User) -> int:
    """Länka olänkade klock-gympass (typ "other") till närmaste loggade
    styrkepass inom ±90 min. Returnerar antal nya länkar."""
    if not auto_merge_enabled(user):
        return 0

    activities = list(
        await db.scalars(
            select(CardioActivity).where(
                CardioActivity.user_id == user.id,
                CardioActivity.type == "other",
                CardioActivity.source.in_(WATCH_SOURCES),
                CardioActivity.linked_session_id.is_(None),
                CardioActivity.autolink_opt_out.is_(False),
            )
        )
    )
    if not activities:
        return 0

    sessions = list(
        await db.scalars(
            select(WorkoutSession).where(
                WorkoutSession.user_id == user.id,
                WorkoutSession.finished_at.is_not(None),
            )
        )
    )
    if not sessions:
        return 0

    # En session ska bara bära ett klockpass
    taken = {
        row
        for row in await db.scalars(
            select(CardioActivity.linked_session_id).where(
                CardioActivity.user_id == user.id,
                CardioActivity.linked_session_id.is_not(None),
            )
        )
    }

    linked = 0
    for activity in activities:
        best: tuple[float, WorkoutSession] | None = None
        for ws in sessions:
            if ws.id in taken:
                continue
            diff = abs(
                (_utc(ws.started_at) - _utc(activity.started_at)).total_seconds()
            )
            if diff <= LINK_WINDOW.total_seconds() and (
                best is None or diff < best[0]
            ):
                best = (diff, ws)
        if best is not None:
            activity.linked_session_id = best[1].id
            taken.add(best[1].id)
            linked += 1

    if linked:
        await db.commit()
    return linked
