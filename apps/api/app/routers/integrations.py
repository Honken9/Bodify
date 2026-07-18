import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
from app.db import get_session
from app.integrations import strava, withings
from app.models import IngestToken, OAuthConnection, User
from app.security import encrypt, hash_token

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

PROVIDERS = ("strava", "withings")


def _make_state(user: User, provider: str) -> str:
    return pyjwt.encode(
        {
            "sub": str(user.id),
            "provider": provider,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        },
        get_settings().secret_key,
        algorithm="HS256",
    )


def _verify_state(state: str, user: User, provider: str) -> None:
    try:
        claims = pyjwt.decode(
            state, get_settings().secret_key, algorithms=["HS256"]
        )
    except pyjwt.PyJWTError:
        raise HTTPException(400, "Ogiltig state-parameter.")
    if claims.get("sub") != str(user.id) or claims.get("provider") != provider:
        raise HTTPException(400, "State matchar inte inloggad användare.")


@router.get("")
async def list_integrations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    connections = {
        c.provider: c
        for c in await db.scalars(
            select(OAuthConnection).where(OAuthConnection.user_id == user.id)
        )
    }
    tokens = list(
        await db.scalars(
            select(IngestToken).where(IngestToken.user_id == user.id)
        )
    )
    return {
        "providers": [
            {
                "provider": p,
                "connected": p in connections,
                "status": connections[p].status if p in connections else None,
                "since": connections[p].created_at.isoformat()
                if p in connections
                else None,
            }
            for p in PROVIDERS
        ],
        "apple_health_tokens": [
            {
                "id": str(t.id),
                "label": t.label,
                "created_at": t.created_at.isoformat(),
                "last_seen_at": t.last_seen_at.isoformat()
                if t.last_seen_at
                else None,
            }
            for t in tokens
        ],
    }


@router.get("/{provider}/connect")
async def connect(
    provider: str,
    user: User = Depends(get_current_user),
) -> dict:
    state = _make_state(user, provider)
    if provider == "strava":
        return {"url": strava.authorize_url(state)}
    if provider == "withings":
        return {"url": withings.authorize_url(state)}
    raise HTTPException(404, "Okänd tjänst.")


@router.get("/strava/callback")
async def strava_callback(
    code: str,
    state: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    _verify_state(state, user, "strava")
    data = await strava.exchange_code(code)
    await _upsert_connection(
        db,
        user,
        provider="strava",
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_at=datetime.fromtimestamp(data["expires_at"], tz=timezone.utc),
        external_user_id=str(data.get("athlete", {}).get("id", "")),
        scopes="activity:read_all",
    )
    return RedirectResponse(url="/settings?connected=strava", status_code=302)


@router.get("/withings/callback")
async def withings_callback(
    code: str,
    state: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    _verify_state(state, user, "withings")
    body = await withings.exchange_code(code)
    conn = await _upsert_connection(
        db,
        user,
        provider="withings",
        access_token=body["access_token"],
        refresh_token=body["refresh_token"],
        expires_at=datetime.now(timezone.utc)
        + timedelta(seconds=int(body.get("expires_in", 10800))),
        external_user_id=str(body.get("userid", "")),
        scopes=withings.SCOPES,
    )
    try:
        await withings.subscribe_notifications(conn, db)
    except Exception:  # prenumerationen kan göras om senare — blockera inte
        pass
    # Hämta historiken direkt så grafer fylls från dag ett
    try:
        measures = await withings.fetch_measures(conn, db)
        from app.models import BodyMetric

        for m in measures:
            await db.merge(
                BodyMetric(
                    user_id=user.id,
                    metric=m["metric"],
                    measured_at=m["measured_at"],
                    source="withings",
                    value=m["value"],
                )
            )
        await db.commit()
    except Exception:
        pass
    # Träningspass + stegräkning — hela historiken (kräver user.activity)
    try:
        from app.routers.webhooks import _sync_withings_workouts_and_steps

        await _sync_withings_workouts_and_steps(conn, db, days_back=3650)
    except Exception:
        pass
    return RedirectResponse(url="/settings?connected=withings", status_code=302)


async def _upsert_connection(
    db: AsyncSession,
    user: User,
    *,
    provider: str,
    access_token: str,
    refresh_token: str,
    expires_at: datetime,
    external_user_id: str,
    scopes: str,
) -> OAuthConnection:
    conn = await db.scalar(
        select(OAuthConnection).where(
            OAuthConnection.user_id == user.id,
            OAuthConnection.provider == provider,
        )
    )
    if conn is None:
        conn = OAuthConnection(user_id=user.id, provider=provider)
        db.add(conn)
    conn.access_token_enc = encrypt(access_token)
    conn.refresh_token_enc = encrypt(refresh_token)
    conn.expires_at = expires_at
    conn.external_user_id = external_user_id
    conn.scopes = scopes
    conn.status = "active"
    await db.commit()
    await db.refresh(conn)
    return conn


@router.delete("/{provider}", status_code=204)
async def disconnect(
    provider: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    conn = await db.scalar(
        select(OAuthConnection).where(
            OAuthConnection.user_id == user.id,
            OAuthConnection.provider == provider,
        )
    )
    if conn is None:
        raise HTTPException(404, "Ingen koppling finns.")
    await db.delete(conn)
    await db.commit()


# ── Apple Health-tokens ───────────────────────────────────────


@router.post("/apple-health/tokens", status_code=201)
async def create_ingest_token(
    payload: dict | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    token = secrets.token_urlsafe(24)
    row = IngestToken(
        user_id=user.id,
        token_hash=hash_token(token),
        label=(payload or {}).get("label", "Apple Health")[:120],
    )
    db.add(row)
    await db.commit()
    settings = get_settings()
    return {
        "id": str(row.id),
        # Visas EN gång — endast hashen sparas
        "token": token,
        "endpoint": f"{settings.public_base_url}/api/webhooks/apple-health",
    }


@router.delete("/apple-health/tokens/{token_id}", status_code=204)
async def revoke_ingest_token(
    token_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    row = await db.get(IngestToken, token_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, "Tokenen finns inte.")
    await db.delete(row)
    await db.commit()
