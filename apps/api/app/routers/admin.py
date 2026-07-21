import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.db import get_session
from app.integrations import cloudflare
from app.integrations.cloudflare import CloudflareError, CloudflareNotConfigured
from app.models import (
    CardioActivity,
    Challenge,
    MealEntry,
    OAuthConnection,
    User,
    WorkoutSession,
)
from app.schemas import UserOut
from app.services import challenges as challenge_service

router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)]
)


@router.get("/users", response_model=list[UserOut])
async def list_users(session: AsyncSession = Depends(get_session)) -> list[User]:
    result = await session.scalars(select(User).order_by(User.created_at))
    return list(result)


class AdminUserUpdate(BaseModel):
    is_admin: bool


class AdminUserCreate(BaseModel):
    email: EmailStr
    display_name: str | None = None
    is_admin: bool = False


@router.post("/users", status_code=201)
async def create_user(
    payload: AdminUserCreate,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Skapa användare direkt — och vitlista i Cloudflare om API:t är satt."""
    email = payload.email.lower().strip()
    existing = await session.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(409, "Användaren finns redan.")

    user = User(
        email=email,
        display_name=(payload.display_name or "").strip() or None,
        is_admin=payload.is_admin,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    whitelisted = False
    if cloudflare.is_configured():
        try:
            await cloudflare.add_email(email)
            whitelisted = True
        except CloudflareError:
            pass  # kontot är skapat; vitlistan får göras manuellt

    return {"user": UserOut.model_validate(user).model_dump(mode="json"),
            "whitelisted": whitelisted}


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Användaren finns inte.")
    if user.id == admin.id and not payload.is_admin:
        raise HTTPException(400, "Du kan inte ta bort din egen adminroll.")
    user.is_admin = payload.is_admin
    await session.commit()
    await session.refresh(user)
    return user


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Radera användaren och ALL dess data (kaskad), städa fotofiler,
    och ta bort adressen ur Cloudflare-vitlistan om API:t är satt."""
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Användaren finns inte.")
    if user.id == admin.id:
        raise HTTPException(400, "Du kan inte radera dig själv.")

    from pathlib import Path

    from app.models import ProgressPhoto

    photos = await session.scalars(
        select(ProgressPhoto).where(ProgressPhoto.user_id == user.id)
    )
    for photo in photos:
        Path(photo.file_path).unlink(missing_ok=True)

    email = user.email
    await session.delete(user)
    await session.commit()

    whitelist_removed = False
    if cloudflare.is_configured():
        try:
            await cloudflare.remove_email(email)
            whitelist_removed = True
        except CloudflareError:
            pass

    return {"ok": True, "whitelist_removed": whitelist_removed}


@router.get("/users/{user_id}/stats")
async def user_stats(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Adminvyns användarkort: aktivitet, senaste händelser och utmaningar."""
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Användaren finns inte.")

    from app.models import (
        BodyMetric,
        ChallengeParticipant,
        ProgressPhoto,
    )
    from app.models import Challenge as ChallengeModel
    from app.models import MealEntry as MealEntryModel

    async def count(stmt) -> int:
        return (await session.scalar(stmt)) or 0

    strength = await count(
        select(func.count(WorkoutSession.id)).where(
            WorkoutSession.user_id == user_id,
            WorkoutSession.finished_at.is_not(None),
        )
    )
    cardio_count = await count(
        select(func.count(CardioActivity.id)).where(
            CardioActivity.user_id == user_id,
            CardioActivity.linked_session_id.is_(None),
        )
    )
    meals = await count(
        select(func.count(MealEntryModel.id)).where(
            MealEntryModel.user_id == user_id
        )
    )
    metrics = await count(
        select(func.count()).select_from(BodyMetric).where(
            BodyMetric.user_id == user_id
        )
    )
    photos = await count(
        select(func.count(ProgressPhoto.id)).where(
            ProgressPhoto.user_id == user_id
        )
    )

    # Senaste passet — styrka eller kondition, det nyaste vinner
    last_session = await session.scalar(
        select(WorkoutSession)
        .where(
            WorkoutSession.user_id == user_id,
            WorkoutSession.finished_at.is_not(None),
        )
        .order_by(WorkoutSession.started_at.desc())
        .limit(1)
    )
    last_cardio = await session.scalar(
        select(CardioActivity)
        .where(
            CardioActivity.user_id == user_id,
            CardioActivity.linked_session_id.is_(None),
        )
        .order_by(CardioActivity.started_at.desc())
        .limit(1)
    )
    last_workout = None
    candidates = []
    if last_session is not None:
        candidates.append(
            (
                last_session.started_at,
                {
                    "kind": "strength",
                    "name": last_session.program_day.name
                    if last_session.program_day
                    else "Styrkepass",
                    "when": last_session.started_at.isoformat(),
                },
            )
        )
    if last_cardio is not None:
        candidates.append(
            (
                last_cardio.started_at,
                {
                    "kind": "cardio",
                    "name": last_cardio.name or "Kondition",
                    "when": last_cardio.started_at.isoformat(),
                },
            )
        )
    if candidates:
        last_workout = max(candidates, key=lambda c: c[0])[1]

    # Senast aktiv = nyaste spåret oavsett typ (pass, måltid, mätning)
    last_meal_at = await session.scalar(
        select(func.max(MealEntryModel.created_at)).where(
            MealEntryModel.user_id == user_id
        )
    )
    last_metric_at = await session.scalar(
        select(func.max(BodyMetric.measured_at)).where(
            BodyMetric.user_id == user_id
        )
    )
    from datetime import timezone as _tz

    def _utc(dt):
        # SQLite ger naiva tidsstämplar, Postgres medvetna — jämför i UTC
        return dt.replace(tzinfo=_tz.utc) if dt.tzinfo is None else dt

    stamps = [
        _utc(s)
        for s in (
            max((c[0] for c in candidates), default=None),
            last_meal_at,
            last_metric_at,
        )
        if s is not None
    ]
    last_activity = max(stamps).isoformat() if stamps else None

    # Utmaningar användaren deltar i
    from datetime import date as _date

    challenge_rows = list(
        await session.scalars(
            select(ChallengeModel)
            .join(
                ChallengeParticipant,
                ChallengeParticipant.challenge_id == ChallengeModel.id,
            )
            .where(ChallengeParticipant.user_id == user_id)
            .order_by(ChallengeModel.ends_on.desc())
        )
    )
    today = _date.today()
    challenges = [
        {
            "name": c.name,
            "active": c.starts_on <= today <= c.ends_on,
            "ends_on": c.ends_on.isoformat(),
        }
        for c in challenge_rows[:10]
    ]

    providers = list(
        await session.scalars(
            select(OAuthConnection.provider).where(
                OAuthConnection.user_id == user_id
            )
        )
    )

    return {
        "workout_sessions": strength,
        "cardio_activities": cardio_count,
        "meal_entries": meals,
        "metrics": metrics,
        "photos": photos,
        "last_activity": last_activity,
        "last_workout": last_workout,
        "challenges": challenges,
        "connections": sorted(providers),
    }


@router.get("/overview")
async def overview(session: AsyncSession = Depends(get_session)) -> dict:
    async def count(stmt) -> int:
        return (await session.scalar(stmt)) or 0

    connections = await session.execute(
        select(
            OAuthConnection.provider, func.count(OAuthConnection.id)
        ).group_by(OAuthConnection.provider)
    )
    return {
        "users": await count(select(func.count(User.id))),
        "workout_sessions": await count(
            select(func.count(WorkoutSession.id)).where(
                WorkoutSession.finished_at.is_not(None)
            )
        ),
        "cardio_activities": await count(select(func.count(CardioActivity.id))),
        "meal_entries": await count(select(func.count(MealEntry.id))),
        "challenges": await count(select(func.count(Challenge.id))),
        "connections": {row[0]: row[1] for row in connections},
    }


@router.post("/jobs/challenge-snapshots")
async def trigger_snapshots(session: AsyncSession = Depends(get_session)) -> dict:
    """Kör snapshot-jobbet manuellt (körs annars nattligt av workern)."""
    return await challenge_service.run_daily_snapshots(session)


# ── Externa testare (Cloudflare Access-vitlistan) ─────────────


class TesterInvite(BaseModel):
    email: EmailStr


def _cf_error(exc: Exception) -> HTTPException:
    if isinstance(exc, CloudflareNotConfigured):
        return HTTPException(503, str(exc))
    return HTTPException(502, f"Cloudflare-API:t svarade med fel: {exc}")


@router.get("/testers")
async def list_testers(session: AsyncSession = Depends(get_session)) -> dict:
    """Vitlistade adresser + om de loggat in ännu."""
    if not cloudflare.is_configured():
        return {"configured": False, "testers": []}
    try:
        emails = await cloudflare.list_allowed_emails()
    except CloudflareError as exc:
        raise _cf_error(exc)

    known = {
        u.email: u
        for u in await session.scalars(
            select(User).where(User.email.in_(emails))
        )
    }
    return {
        "configured": True,
        "testers": [
            {
                "email": email,
                "has_logged_in": email in known,
                "display_name": known[email].display_name
                if email in known
                else None,
            }
            for email in emails
        ],
    }


@router.post("/testers", status_code=201)
async def invite_tester(payload: TesterInvite) -> dict:
    try:
        emails = await cloudflare.add_email(payload.email)
    except (CloudflareNotConfigured, CloudflareError) as exc:
        raise _cf_error(exc)
    return {"ok": True, "emails": emails}


@router.delete("/testers/{email}")
async def remove_tester(
    email: str,
    admin: User = Depends(require_admin),
) -> dict:
    if email.lower().strip() == admin.email:
        raise HTTPException(400, "Du kan inte ta bort din egen åtkomst.")
    try:
        emails = await cloudflare.remove_email(email)
    except (CloudflareNotConfigured, CloudflareError) as exc:
        raise _cf_error(exc)
    return {"ok": True, "emails": emails}
