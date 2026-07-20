import uuid
from datetime import date, timedelta

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
    ChallengeInvite,
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
    kind: str = Field(default="standard", pattern="^(standard|habit)$")
    target_per_week: int | None = Field(default=None, ge=1, le=7)
    is_open: bool = False


METRIC_LABELS = {
    "workout_count": "Flest pass",
    "distance_km": "Längst distans",
    "weight_loss_kg": "Störst viktnedgång",
    "fat_loss_percent": "Störst fettnedgång",
    "steps_total": "Flest steg",
    "sleep_score_avg": "Bäst sömnpoäng (snitt)",
    "sleep_hours_avg": "Mest sömn (snitt h/natt)",
    "active_days": "Flest aktiva dagar",
    "workout_minutes": "Flest träningsminuter",
    "logged_days": "Flest loggade kostdagar",
}

METRIC_UNITS = {
    "workout_count": "pass",
    "distance_km": "km",
    "weight_loss_kg": "kg",
    "fat_loss_percent": "%-enheter",
    "steps_total": "steg",
    "sleep_score_avg": "poäng",
    "sleep_hours_avg": "h",
    "active_days": "dagar",
    "workout_minutes": "min",
    "logged_days": "dagar",
}


def _metric_label(challenge: Challenge) -> str:
    if challenge.kind == "habit":
        per_week = (challenge.target or {}).get("per_week", 3)
        return f"Vana: {per_week} pass/vecka"
    return METRIC_LABELS.get(challenge.metric, challenge.metric)


def _challenge_out(
    challenge: Challenge, me: User, invited: bool = False
) -> dict:
    today = date.today()
    return {
        "id": str(challenge.id),
        "name": challenge.name,
        "metric": challenge.metric,
        "metric_label": _metric_label(challenge),
        "unit": METRIC_UNITS.get(challenge.metric, ""),
        "kind": challenge.kind,
        "target": challenge.target,
        "is_open": challenge.is_open,
        "starts_on": challenge.starts_on.isoformat(),
        "ends_on": challenge.ends_on.isoformat(),
        "days_left": max((challenge.ends_on - today).days, 0),
        "finished": challenge.ends_on < today,
        "participant_count": len(challenge.participants),
        "is_participant": any(
            p.user_id == me.id for p in challenge.participants
        ),
        "is_creator": challenge.creator_id == me.id,
        "invited": invited,
        "active": challenge.starts_on <= today <= challenge.ends_on,
    }


async def _invite_for(
    db: AsyncSession, challenge_id: uuid.UUID, user_id: uuid.UUID
) -> ChallengeInvite | None:
    return await db.scalar(
        select(ChallengeInvite).where(
            ChallengeInvite.challenge_id == challenge_id,
            ChallengeInvite.user_id == user_id,
        )
    )


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
    invited_ids = {
        row
        for row in await db.scalars(
            select(ChallengeInvite.challenge_id).where(
                ChallengeInvite.user_id == user.id
            )
        )
    }
    reachable = joined_ids | invited_ids
    rows = list(
        await db.scalars(
            select(Challenge)
            .where(
                or_(
                    Challenge.creator_id.in_(visible_creators),
                    Challenge.id.in_(reachable) if reachable else False,
                    # Öppna, aktuella utmaningar (t.ex. veckoutmaningarna)
                    # syns för alla så vem som helst kan hoppa på
                    (Challenge.is_open.is_(True))
                    & (Challenge.ends_on >= date.today()),
                )
            )
            .order_by(Challenge.ends_on.desc())
        )
    )
    return [
        _challenge_out(c, user, invited=c.id in invited_ids) for c in rows
    ]


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
    if payload.kind == "habit" and not payload.target_per_week:
        raise HTTPException(400, "Vaneutmaning kräver antal pass per vecka.")

    challenge = Challenge(
        creator_id=user.id,
        name=payload.name,
        # Vanor mäts alltid i pass — målet är X pass/vecka
        metric="workout_count" if payload.kind == "habit" else payload.metric,
        starts_on=payload.starts_on,
        ends_on=payload.ends_on,
        kind=payload.kind,
        target=(
            {"per_week": payload.target_per_week}
            if payload.kind == "habit"
            else None
        ),
        is_open=payload.is_open,
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

    invite = await _invite_for(db, challenge.id, user.id)
    friend_ids = await _friend_ids(db, user)
    if (
        not challenge.is_open
        and challenge.creator_id != user.id
        and challenge.creator_id not in friend_ids
        and invite is None
    ):
        raise HTTPException(
            403, "Du kan bara gå med i vänners utmaningar eller via inbjudan."
        )
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
    if invite is not None:
        await db.delete(invite)  # inbjudan förbrukad
    await db.commit()
    await push.send_to_user(
        db,
        challenge.creator_id,
        "Ny deltagare 🎉",
        f"{user.display_name or user.email} gick med i \"{challenge.name}\".",
        url="/social",
    )
    return {"ok": True}


@router.get("/challenges/active-summary")
async def active_challenge_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Hemskärmens utmaningskort: min placering + gapet till nästa."""
    today = date.today()
    rows = list(
        await db.scalars(
            select(Challenge)
            .join(
                ChallengeParticipant,
                ChallengeParticipant.challenge_id == Challenge.id,
            )
            .where(
                ChallengeParticipant.user_id == user.id,
                Challenge.starts_on <= today,
                Challenge.ends_on >= today,
            )
            .order_by(Challenge.ends_on)
        )
    )
    result = []
    for challenge in rows[:3]:
        board = await challenge_service.leaderboard(db, challenge)
        mine = next((r for r in board if r["user_id"] == str(user.id)), None)
        if mine is None:
            continue
        entry = {
            "id": str(challenge.id),
            "name": challenge.name,
            "kind": challenge.kind,
            "metric_label": _metric_label(challenge),
            "unit": METRIC_UNITS.get(challenge.metric, ""),
            "days_left": (challenge.ends_on - today).days,
            "my_rank": mine["rank"],
            "my_value": mine["value"],
            "participants": len(board),
            "gap_ahead": None,
            "gap_behind": None,
        }
        if challenge.kind == "habit":
            completed, total = await challenge_service.habit_weeks_completed(
                db, challenge, user.id
            )
            entry["habit"] = {
                "completed": completed,
                "total": total,
                "per_week": (challenge.target or {}).get("per_week", 3),
            }
        else:
            ahead = next(
                (r for r in board if r["rank"] == mine["rank"] - 1), None
            )
            behind = next(
                (r for r in board if r["rank"] == mine["rank"] + 1), None
            )
            if ahead is not None:
                entry["gap_ahead"] = {
                    "name": ahead["name"],
                    "diff": round(ahead["value"] - mine["value"], 1),
                }
            if behind is not None:
                entry["gap_behind"] = {
                    "name": behind["name"],
                    "diff": round(mine["value"] - behind["value"], 1),
                }
        result.append(entry)
    return result


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
    invite = await _invite_for(db, challenge.id, user.id)
    if (
        not is_participant
        and not challenge.is_open  # öppna utmaningar får granskas före join
        and invite is None
        and challenge.creator_id not in friend_ids | {user.id}
    ):
        raise HTTPException(404, "Utmaningen finns inte.")

    board = await challenge_service.leaderboard(db, challenge)
    result = {
        **_challenge_out(challenge, user, invited=invite is not None),
        "leaderboard": board,
        "history": await challenge_service.history(db, challenge),
    }
    if challenge.kind == "habit" and any(
        p.user_id == user.id for p in challenge.participants
    ):
        completed, total = await challenge_service.habit_weeks_completed(
            db, challenge, user.id
        )
        result["habit"] = {"completed": completed, "total": total}
    return result


class InviteRequest(BaseModel):
    email: str = Field(max_length=320)


@router.post("/challenges/{challenge_id}/invite", status_code=201)
async def invite_to_challenge(
    challenge_id: uuid.UUID,
    payload: InviteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Bjud in en annan användare — alla deltagare i utmaningen kan bjuda in,
    och den inbjudna behöver inte vara vän med skaparen."""
    challenge = await db.get(Challenge, challenge_id)
    if challenge is None:
        raise HTTPException(404, "Utmaningen finns inte.")
    if not any(p.user_id == user.id for p in challenge.participants):
        raise HTTPException(403, "Bara deltagare kan bjuda in.")

    target = await db.scalar(
        select(User).where(User.email == payload.email.lower().strip())
    )
    if target is None:
        raise HTTPException(
            404,
            "Ingen användare med den adressen — be personen logga in en "
            "första gång (adressen måste vara vitlistad).",
        )
    if any(p.user_id == target.id for p in challenge.participants):
        raise HTTPException(409, "Personen är redan med i utmaningen.")
    if await _invite_for(db, challenge.id, target.id) is not None:
        return {"ok": True, "already_invited": True}

    db.add(
        ChallengeInvite(
            challenge_id=challenge.id, user_id=target.id, invited_by=user.id
        )
    )
    await db.commit()
    await push.send_to_user(
        db,
        target.id,
        "Inbjudan till utmaning 🏆",
        f"{user.display_name or user.email} har bjudit in dig till "
        f"\"{challenge.name}\" — häng på!",
        url="/social",
    )
    return {"ok": True}


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


# ── Aktivitetsflöde & heja ────────────────────────────────────


async def _require_participant(
    db: AsyncSession, challenge_id: uuid.UUID, user: User
) -> Challenge:
    challenge = await db.get(Challenge, challenge_id)
    if challenge is None or not any(
        p.user_id == user.id for p in challenge.participants
    ):
        raise HTTPException(404, "Utmaningen finns inte.")
    return challenge


@router.get("/challenges/{challenge_id}/feed")
async def challenge_feed(
    challenge_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Senaste händelserna i utmaningen — pass från alla deltagare,
    med 👏-räknare."""
    from datetime import datetime, time, timedelta, timezone

    from app.models import CardioActivity, ChallengeCheer, WorkoutSession

    challenge = await _require_participant(db, challenge_id, user)
    participant_ids = [p.user_id for p in challenge.participants]
    names = {}
    for pid in participant_ids:
        u = await db.get(User, pid)
        names[pid] = (u.display_name or u.email.split("@")[0]) if u else "?"

    start = datetime.combine(challenge.starts_on, time.min, tzinfo=timezone.utc)
    end = datetime.combine(
        challenge.ends_on + timedelta(days=1), time.min, tzinfo=timezone.utc
    )

    items: list[dict] = []
    for s in await db.scalars(
        select(WorkoutSession).where(
            WorkoutSession.user_id.in_(participant_ids),
            WorkoutSession.finished_at.is_not(None),
            WorkoutSession.started_at >= start,
            WorkoutSession.started_at < end,
        )
    ):
        items.append(
            {
                "kind": "strength",
                "id": str(s.id),
                "user_id": str(s.user_id),
                "user_name": names.get(s.user_id, "?"),
                "title": s.program_day.name if s.program_day else "Styrkepass",
                "when": s.started_at.isoformat(),
                "detail": None,
            }
        )
    for a in await db.scalars(
        select(CardioActivity).where(
            CardioActivity.user_id.in_(participant_ids),
            CardioActivity.started_at >= start,
            CardioActivity.started_at < end,
            CardioActivity.linked_session_id.is_(None),
        )
    ):
        detail = []
        if a.distance_m:
            detail.append(f"{float(a.distance_m) / 1000:.1f} km")
        detail.append(f"{round(a.duration_s / 60)} min")
        items.append(
            {
                "kind": "cardio",
                "id": str(a.id),
                "user_id": str(a.user_id),
                "user_name": names.get(a.user_id, "?"),
                "title": a.name or "Kondition",
                "when": a.started_at.isoformat(),
                "detail": " · ".join(detail),
            }
        )
    items.sort(key=lambda i: i["when"], reverse=True)
    items = items[:25]

    cheers = list(
        await db.scalars(
            select(ChallengeCheer).where(
                ChallengeCheer.challenge_id == challenge.id
            )
        )
    )
    for item in items:
        mine = [
            c
            for c in cheers
            if c.item_kind == item["kind"] and c.item_id == item["id"]
        ]
        item["cheers"] = len(mine)
        item["cheered_by_me"] = any(c.actor_id == user.id for c in mine)
    return items


class CheerRequest(BaseModel):
    item_kind: str = Field(pattern="^(strength|cardio)$")
    item_id: str = Field(max_length=64)
    owner_id: uuid.UUID


@router.post("/challenges/{challenge_id}/cheer")
async def cheer(
    challenge_id: uuid.UUID,
    payload: CheerRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """👏 på en händelse i flödet — en gång per person, togglas av."""
    from app.models import ChallengeCheer

    challenge = await _require_participant(db, challenge_id, user)
    # Mottagaren måste vara deltagare — annars kan pushen riktas mot
    # godtycklig användare på servern
    if payload.owner_id not in {p.user_id for p in challenge.participants}:
        raise HTTPException(400, "Mottagaren är inte med i utmaningen.")
    existing = await db.scalar(
        select(ChallengeCheer).where(
            ChallengeCheer.challenge_id == challenge.id,
            ChallengeCheer.item_kind == payload.item_kind,
            ChallengeCheer.item_id == payload.item_id,
            ChallengeCheer.actor_id == user.id,
        )
    )
    if existing is not None:
        await db.delete(existing)
        await db.commit()
        return {"ok": True, "cheered": False}

    db.add(
        ChallengeCheer(
            challenge_id=challenge.id,
            item_kind=payload.item_kind,
            item_id=payload.item_id,
            actor_id=user.id,
        )
    )
    await db.commit()
    if payload.owner_id != user.id:
        await push.send_to_user(
            db,
            payload.owner_id,
            "👏 Du fick en heja!",
            f"{user.display_name or user.email.split('@')[0]} hejade på ditt "
            f"pass i \"{challenge.name}\".",
            url="/social",
        )
    return {"ok": True, "cheered": True}


# ── Troféer & revansch ────────────────────────────────────────


@router.get("/trophies")
async def my_trophies(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await challenge_service.trophies(db, user.id)


@router.post("/challenges/{challenge_id}/rematch", status_code=201)
async def rematch(
    challenge_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Skapa en ny omgång av en avgjord utmaning — samma upplägg, start
    idag, och alla gamla deltagare bjuds in automatiskt."""
    old = await _require_participant(db, challenge_id, user)
    if old.ends_on >= date.today():
        raise HTTPException(400, "Utmaningen pågår fortfarande.")

    length = (old.ends_on - old.starts_on).days
    base_name = old.name.split(" · revansch")[0]
    new = Challenge(
        creator_id=user.id,
        name=f"{base_name} · revansch"[:120],
        metric=old.metric,
        starts_on=date.today(),
        ends_on=date.today() + timedelta(days=length),
        kind="standard" if old.kind == "weekly" else old.kind,
        target=old.target,
        is_open=old.is_open,
    )
    baseline = await challenge_service.snapshot_baseline(db, user.id, old.metric)
    new.participants.append(
        ChallengeParticipant(user_id=user.id, baseline=baseline)
    )
    db.add(new)
    await db.commit()

    for p in old.participants:
        if p.user_id == user.id:
            continue
        db.add(
            ChallengeInvite(
                challenge_id=new.id, user_id=p.user_id, invited_by=user.id
            )
        )
        await push.send_to_user(
            db,
            p.user_id,
            "Revansch! 🔄",
            f"{user.display_name or user.email.split('@')[0]} utmanar dig "
            f"igen i \"{new.name}\" — våga vägra förlora två gånger.",
            url="/social",
        )
    await db.commit()
    new = await db.scalar(
        select(Challenge)
        .where(Challenge.id == new.id)
        .execution_options(populate_existing=True)
    )
    return _challenge_out(new, user)
