import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import push
from app.auth import get_current_user
from app.db import get_session
from app.models import (
    CHALLENGE_METRICS,
    Challenge,
    ChallengeParticipant,
    Friendship,
    User,
)
from app.services import challenges as challenge_service

router = APIRouter(prefix="/api/social", tags=["social"])


# ── Vänner ────────────────────────────────────────────────────


class FriendRequest(BaseModel):
    email: str = Field(max_length=320)


async def _friend_ids(db: AsyncSession, user: User) -> set[uuid.UUID]:
    """Accepterade vänner (båda riktningarna)."""
    rows = await db.scalars(
        select(Friendship).where(
            Friendship.status == "accepted",
            or_(Friendship.user_id == user.id, Friendship.friend_id == user.id),
        )
    )
    ids = set()
    for f in rows:
        ids.add(f.friend_id if f.user_id == user.id else f.user_id)
    return ids


async def _user_brief(db: AsyncSession, user_id: uuid.UUID) -> dict:
    u = await db.get(User, user_id)
    return {
        "id": str(user_id),
        "name": (u.display_name or u.email.split("@")[0]) if u else "?",
        "email": u.email if u else None,
    }


@router.get("/friends")
async def list_friends(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    rows = list(
        await db.scalars(
            select(Friendship).where(
                or_(
                    Friendship.user_id == user.id,
                    Friendship.friend_id == user.id,
                )
            )
        )
    )
    friends, incoming, outgoing = [], [], []
    for f in rows:
        other_id = f.friend_id if f.user_id == user.id else f.user_id
        entry = {"friendship_id": str(f.id), **await _user_brief(db, other_id)}
        if f.status == "accepted":
            friends.append(entry)
        elif f.friend_id == user.id:
            incoming.append(entry)
        else:
            outgoing.append(entry)
    return {"friends": friends, "incoming": incoming, "outgoing": outgoing}


@router.post("/friends", status_code=201)
async def add_friend(
    payload: FriendRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    other = await db.scalar(
        select(User).where(User.email == payload.email.lower().strip())
    )
    if other is None:
        raise HTTPException(
            404,
            "Ingen användare med den adressen — be din vän logga in en "
            "första gång (och se till att adressen är vitlistad i Cloudflare).",
        )
    if other.id == user.id:
        raise HTTPException(400, "Du kan inte lägga till dig själv.")

    existing = await db.scalar(
        select(Friendship).where(
            or_(
                (Friendship.user_id == user.id)
                & (Friendship.friend_id == other.id),
                (Friendship.user_id == other.id)
                & (Friendship.friend_id == user.id),
            )
        )
    )
    if existing is not None:
        raise HTTPException(409, "Förfrågan eller vänskap finns redan.")

    db.add(Friendship(user_id=user.id, friend_id=other.id))
    await db.commit()
    await push.send_to_user(
        db,
        other.id,
        "Ny vänförfrågan 👋",
        f"{user.display_name or user.email} vill bli din vän i Bodify.",
        url="/social",
    )
    return {"ok": True}


@router.post("/friends/{friendship_id}/accept")
async def accept_friend(
    friendship_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    friendship = await db.get(Friendship, friendship_id)
    if friendship is None or friendship.friend_id != user.id:
        raise HTTPException(404, "Förfrågan finns inte.")
    friendship.status = "accepted"
    await db.commit()
    await push.send_to_user(
        db,
        friendship.user_id,
        "Vänförfrågan accepterad ✅",
        f"{user.display_name or user.email} accepterade din förfrågan.",
        url="/social",
    )
    return {"ok": True}


@router.delete("/friends/{friendship_id}", status_code=204)
async def remove_friend(
    friendship_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    friendship = await db.get(Friendship, friendship_id)
    if friendship is None or user.id not in (
        friendship.user_id,
        friendship.friend_id,
    ):
        raise HTTPException(404, "Vänskapen finns inte.")
    await db.delete(friendship)
    await db.commit()


# ── Utmaningar ────────────────────────────────────────────────


class ChallengeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    metric: str
    starts_on: date
    ends_on: date


METRIC_LABELS = {
    "workout_count": "Flest pass",
    "distance_km": "Längst distans",
    "weight_loss_kg": "Störst viktnedgång",
    "fat_loss_percent": "Störst fettnedgång",
}


def _challenge_out(challenge: Challenge, me: User) -> dict:
    return {
        "id": str(challenge.id),
        "name": challenge.name,
        "metric": challenge.metric,
        "metric_label": METRIC_LABELS.get(challenge.metric, challenge.metric),
        "starts_on": challenge.starts_on.isoformat(),
        "ends_on": challenge.ends_on.isoformat(),
        "participant_count": len(challenge.participants),
        "is_participant": any(
            p.user_id == me.id for p in challenge.participants
        ),
        "is_creator": challenge.creator_id == me.id,
        "active": challenge.starts_on <= date.today() <= challenge.ends_on,
    }


@router.get("/challenges")
async def list_challenges(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[dict]:
    friend_ids = await _friend_ids(db, user)
    visible_creators = friend_ids | {user.id}

    joined_ids = {
        row
        for row in await db.scalars(
            select(ChallengeParticipant.challenge_id).where(
                ChallengeParticipant.user_id == user.id
            )
        )
    }
    rows = list(
        await db.scalars(
            select(Challenge)
            .where(
                or_(
                    Challenge.creator_id.in_(visible_creators),
                    Challenge.id.in_(joined_ids) if joined_ids else False,
                )
            )
            .order_by(Challenge.ends_on.desc())
        )
    )
    return [_challenge_out(c, user) for c in rows]


@router.post("/challenges", status_code=201)
async def create_challenge(
    payload: ChallengeCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    if payload.metric not in CHALLENGE_METRICS:
        raise HTTPException(400, "Okänt tävlingsmätetal.")
    if payload.ends_on < payload.starts_on:
        raise HTTPException(400, "Slutdatum före startdatum.")

    challenge = Challenge(
        creator_id=user.id,
        name=payload.name,
        metric=payload.metric,
        starts_on=payload.starts_on,
        ends_on=payload.ends_on,
    )
    baseline = await challenge_service.snapshot_baseline(
        db, user.id, payload.metric
    )
    challenge.participants.append(
        ChallengeParticipant(user_id=user.id, baseline=baseline)
    )
    db.add(challenge)
    await db.commit()
    challenge = await db.scalar(
        select(Challenge)
        .where(Challenge.id == challenge.id)
        .execution_options(populate_existing=True)
    )
    return _challenge_out(challenge, user)


@router.post("/challenges/{challenge_id}/join")
async def join_challenge(
    challenge_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    challenge = await db.get(Challenge, challenge_id)
    if challenge is None:
        raise HTTPException(404, "Utmaningen finns inte.")

    friend_ids = await _friend_ids(db, user)
    if challenge.creator_id != user.id and challenge.creator_id not in friend_ids:
        raise HTTPException(403, "Du kan bara gå med i vänners utmaningar.")
    if any(p.user_id == user.id for p in challenge.participants):
        raise HTTPException(409, "Du är redan med.")

    baseline = await challenge_service.snapshot_baseline(
        db, user.id, challenge.metric
    )
    if challenge.metric in ("weight_loss_kg", "fat_loss_percent") and not baseline:
        raise HTTPException(
            400,
            "Utmaningen kräver en startmätning — logga eller synka vikt/"
            "kroppsfett först.",
        )
    db.add(
        ChallengeParticipant(
            challenge_id=challenge.id, user_id=user.id, baseline=baseline
        )
    )
    await db.commit()
    await push.send_to_user(
        db,
        challenge.creator_id,
        "Ny deltagare 🎉",
        f"{user.display_name or user.email} gick med i \"{challenge.name}\".",
        url="/social",
    )
    return {"ok": True}


@router.get("/challenges/{challenge_id}")
async def challenge_detail(
    challenge_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    challenge = await db.get(Challenge, challenge_id)
    if challenge is None:
        raise HTTPException(404, "Utmaningen finns inte.")
    friend_ids = await _friend_ids(db, user)
    is_participant = any(p.user_id == user.id for p in challenge.participants)
    if not is_participant and challenge.creator_id not in friend_ids | {user.id}:
        raise HTTPException(404, "Utmaningen finns inte.")

    board = await challenge_service.leaderboard(db, challenge)
    return {
        **_challenge_out(challenge, user),
        "leaderboard": board,
    }


@router.delete("/challenges/{challenge_id}", status_code=204)
async def delete_challenge(
    challenge_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    challenge = await db.get(Challenge, challenge_id)
    if challenge is None or challenge.creator_id != user.id:
        raise HTTPException(404, "Utmaningen finns inte.")
    await db.delete(challenge)
    await db.commit()
