"""Shapiqo-ligan: Elo-rating som justeras när tävlingar avgörs.

Varje avgjord tävling (ej vanor) betygsätts en gång: alla deltagarpar
jämförs och poäng flyttas — vinst mot högre rankad ger mer, förlust mot
lägre kostar mer. K=32 ger snabba, kännbara svängningar i en liten liga.
"""

import logging
import uuid
from datetime import date, timedelta
from itertools import combinations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import push
from app.models import Challenge, ChallengeSnapshot, User

logger = logging.getLogger(__name__)

K_FACTOR = 32


async def rate_finished_challenges(db: AsyncSession) -> dict:
    """Betygsätt alla avgjorda, obetygsatta tävlingar. Delar även ut
    vinst- och comeback-märken. Körs av nattjobbet — idempotent via
    rated-flaggan."""
    from app.services import badges as badge_service
    from app.services import challenges as challenge_service

    today = date.today()
    rows = list(
        await db.scalars(
            select(Challenge).where(
                Challenge.ends_on < today,
                Challenge.rated.is_(False),
                Challenge.kind != "habit",
            )
        )
    )
    rated = 0
    for challenge in rows:
        board = await challenge_service.leaderboard(db, challenge)
        challenge.rated = True
        rated += 1
        if len(board) < 2:
            continue

        users: dict[str, User] = {}
        for row in board:
            u = await db.get(User, uuid.UUID(row["user_id"]))
            if u is not None:
                users[row["user_id"]] = u
        pre = {uid: u.elo_rating for uid, u in users.items()}
        delta: dict[str, float] = {uid: 0.0 for uid in users}

        for a, b in combinations(board, 2):
            if a["user_id"] not in pre or b["user_id"] not in pre:
                continue
            if a["value"] == b["value"]:
                score_a = 0.5
            else:
                score_a = 1.0 if a["rank"] < b["rank"] else 0.0
            expected_a = 1 / (
                1 + 10 ** ((pre[b["user_id"]] - pre[a["user_id"]]) / 400)
            )
            delta[a["user_id"]] += K_FACTOR * (score_a - expected_a)
            delta[b["user_id"]] += K_FACTOR * ((1 - score_a) - (1 - expected_a))

        for uid, change in delta.items():
            users[uid].elo_rating = max(100, round(pre[uid] + change))

        # Vinnarens märken: vinster + ev. comeback (sist vid halvtid)
        winner = board[0]
        winner_uuid = uuid.UUID(winner["user_id"])
        wins = await _count_wins(db, winner_uuid)
        if wins >= 1:
            await badge_service.award(db, winner_uuid, "wins_1")
        if wins >= 5:
            await badge_service.award(db, winner_uuid, "wins_5")
        if await _was_last_at_halftime(db, challenge, winner["user_id"]):
            await badge_service.award(db, winner_uuid, "comeback")

    await db.commit()
    if rated:
        logger.info("Elo: %s tävlingar betygsatta.", rated)
    return {"rated": rated}


async def _count_wins(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Antal vunna (rank 1) avgjorda tävlingar — litet antal, räknas om."""
    from app.services import challenges as challenge_service

    trophies = await challenge_service.trophies(db, user_id)
    return sum(
        1 for t in trophies if t["rank"] == 1 and t["kind"] != "habit"
    )


async def _was_last_at_halftime(
    db: AsyncSession, challenge: Challenge, winner_id: str
) -> bool:
    midpoint = challenge.starts_on + timedelta(
        days=(challenge.ends_on - challenge.starts_on).days // 2
    )
    rows = list(
        await db.scalars(
            select(ChallengeSnapshot).where(
                ChallengeSnapshot.challenge_id == challenge.id,
                ChallengeSnapshot.day == midpoint,
            )
        )
    )
    if len(rows) < 2:
        return False
    worst = min(rows, key=lambda r: float(r.value))
    return str(worst.user_id) == winner_id and any(
        float(r.value) > float(worst.value) for r in rows
    )


async def head_to_head(
    db: AsyncSession, user_a: uuid.UUID, user_b: uuid.UUID
) -> dict:
    """Inbördes möten: avgjorda dueller mellan två användare."""
    from app.models import ChallengeParticipant
    from app.services import challenges as challenge_service

    today = date.today()
    a_challenges = {
        row
        for row in await db.scalars(
            select(ChallengeParticipant.challenge_id).where(
                ChallengeParticipant.user_id == user_a
            )
        )
    }
    duels = list(
        await db.scalars(
            select(Challenge)
            .join(
                ChallengeParticipant,
                ChallengeParticipant.challenge_id == Challenge.id,
            )
            .where(
                Challenge.kind == "duel",
                Challenge.ends_on < today,
                Challenge.id.in_(a_challenges) if a_challenges else False,
                ChallengeParticipant.user_id == user_b,
            )
        )
    )
    wins_a = wins_b = 0
    for duel in duels:
        board = await challenge_service.leaderboard(db, duel)
        if not board or all(r["value"] == 0 for r in board):
            continue
        if board[0]["user_id"] == str(user_a):
            wins_a += 1
        elif board[0]["user_id"] == str(user_b):
            wins_b += 1
    return {"wins_a": wins_a, "wins_b": wins_b, "duels": len(duels)}
