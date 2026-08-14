"""Prestationsmärken — tävling mot systemet, inte bara mot varandra.

Datadrivna märken utvärderas i nattjobbet; vinst- och comeback-märken
delas ut av ligan när tävlingar betygsätts. Ett märke låses upp en gång
och pushas till användaren."""

import logging
import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import push
from app.models import (
    Badge,
    BodyMetric,
    CardioActivity,
    MealEntry,
    User,
    WorkoutSession,
)

logger = logging.getLogger(__name__)

# key → (emoji, titel, beskrivning)
BADGES: dict[str, tuple[str, str, str]] = {
    "first_10k": ("🏃", "Första milen", "Ett pass på minst 10 km"),
    "workouts_10": ("💪", "Tio pass", "10 loggade pass totalt"),
    "workouts_100": ("🏭", "Hundraklubben", "100 loggade pass totalt"),
    "steps_20k": ("👟", "20 000-dagen", "20 000 steg på en och samma dag"),
    "log_streak_7": ("🥗", "Loggveckan", "Kost loggad 7 dagar i rad"),
    "log_streak_30": ("📅", "Loggmånaden", "Kost loggad 30 dagar i rad"),
    "wins_1": ("🏆", "Första vinsten", "Vann en utmaning eller duell"),
    "wins_5": ("👑", "Femfaldig mästare", "Fem vunna tävlingar"),
    "comeback": ("🃏", "Comeback kid", "Vann efter att ha legat sist vid halvtid"),
}


async def award(db: AsyncSession, user_id: uuid.UUID, key: str) -> bool:
    """Lås upp ett märke (idempotent). Pushar vid ny upplåsning."""
    if key not in BADGES:
        return False
    existing = await db.get(Badge, (user_id, key))
    if existing is not None:
        return False
    db.add(Badge(user_id=user_id, key=key))
    await db.commit()
    emoji, title, description = BADGES[key]
    await push.send_to_user(
        db,
        user_id,
        f"{emoji} Nytt märke: {title}!",
        description,
        url="/profile",
    )
    return True


async def evaluate_user(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Kontrollera datadrivna märken för en användare. Returnerar antal nya."""
    owned = {
        row
        for row in await db.scalars(
            select(Badge.key).where(Badge.user_id == user_id)
        )
    }
    new = 0

    async def check(key: str, earned: bool) -> None:
        nonlocal new
        if earned and key not in owned:
            if await award(db, user_id, key):
                new += 1

    if "first_10k" not in owned:
        run_10k = await db.scalar(
            select(CardioActivity.id)
            .where(
                CardioActivity.user_id == user_id,
                CardioActivity.distance_m >= 10000,
            )
            .limit(1)
        )
        await check("first_10k", run_10k is not None)

    if "workouts_10" not in owned or "workouts_100" not in owned:
        strength = await db.scalar(
            select(func.count(WorkoutSession.id)).where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.finished_at.is_not(None),
            )
        )
        cardio = await db.scalar(
            select(func.count(CardioActivity.id)).where(
                CardioActivity.user_id == user_id,
                CardioActivity.linked_session_id.is_(None),
            )
        )
        total = (strength or 0) + (cardio or 0)
        await check("workouts_10", total >= 10)
        await check("workouts_100", total >= 100)

    if "steps_20k" not in owned:
        big_day = await db.scalar(
            select(BodyMetric.value)
            .where(
                BodyMetric.user_id == user_id,
                BodyMetric.metric == "steps",
                BodyMetric.value >= 20000,
            )
            .limit(1)
        )
        await check("steps_20k", big_day is not None)

    if "log_streak_7" not in owned or "log_streak_30" not in owned:
        days = sorted(
            {
                row
                for row in await db.scalars(
                    select(func.distinct(MealEntry.eaten_on)).where(
                        MealEntry.user_id == user_id
                    )
                )
            }
        )
        best = streak = 0
        prev = None
        for day in days:
            streak = streak + 1 if prev == day - timedelta(days=1) else 1
            best = max(best, streak)
            prev = day
        await check("log_streak_7", best >= 7)
        await check("log_streak_30", best >= 30)

    return new


async def evaluate_all(db: AsyncSession) -> int:
    """Nattjobbet: gå igenom alla användare."""
    total = 0
    for user in await db.scalars(select(User)):
        total += await evaluate_user(db, user.id)
    if total:
        logger.info("Märken: %s nya utdelade.", total)
    return total


async def user_badges(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    """Hela katalogen med upplåst-status — profilens märkesvägg."""
    earned = {
        b.key: b.earned_at
        for b in await db.scalars(
            select(Badge).where(Badge.user_id == user_id)
        )
    }
    return [
        {
            "key": key,
            "emoji": emoji,
            "title": title,
            "description": description,
            "earned": key in earned,
            "earned_at": earned[key].isoformat() if key in earned else None,
        }
        for key, (emoji, title, description) in BADGES.items()
    ]
