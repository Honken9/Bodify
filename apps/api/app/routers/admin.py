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
