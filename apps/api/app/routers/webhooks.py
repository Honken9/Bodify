"""Inkommande webhooks — undantagna från Cloudflare Access men skyddade
med egna hemligheter (Strava verify-token, Withings-koppling via userid,
Apple Health via personlig Bearer-token)."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.integrations import apple_health, strava, withings
from app.models import BodyMetric, CardioActivity, IngestToken, OAuthConnection, User
from app.security import hash_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


# ── Strava ────────────────────────────────────────────────────


@router.get("/strava")
async def strava_verify(
    request: Request,
) -> dict:
    """Prenumerationsvalidering: eka hub.challenge om verify_token stämmer."""
    params = request.query_params
    if params.get("hub.verify_token") != get_settings().strava_verify_token:
        raise HTTPException(403, "Fel verify_token.")
    return {"hub.challenge": params.get("hub.challenge", "")}


@router.post("/strava")
async def strava_event(
    event: dict,
    db: AsyncSession = Depends(get_session),
) -> dict:
    if event.get("object_type") != "activity" or event.get("aspect_type") not in (
        "create",
        "update",
    ):
        return {"ok": True, "ignored": True}

    conn = await db.scalar(
        select(OAuthConnection).where(
            OAuthConnection.provider == "strava",
            OAuthConnection.external_user_id == str(event.get("owner_id")),
        )
    )
    if conn is None:
        return {"ok": True, "ignored": True}

    activity = await strava.fetch_activity(conn, db, str(event["object_id"]))
    if activity is None:
        return {"ok": True, "ignored": True}

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
        db.add(CardioActivity(user_id=conn.user_id, source="strava", **fields))
    await db.commit()
    return {"ok": True}


# ── Withings ──────────────────────────────────────────────────


@router.head("/withings")
async def withings_head() -> PlainTextResponse:
    """Withings validerar callback-URL:en med en HEAD-request."""
    return PlainTextResponse("")


async def _sync_withings_workouts_and_steps(
    conn: OAuthConnection, db: AsyncSession, days_back: int = 7
) -> dict:
    """Hämta träningspass + daglig stegräkning och upserta idempotent."""
    workouts = await withings.fetch_workouts(conn, db, days_back=days_back)
    for fields in workouts:
        existing = await db.scalar(
            select(CardioActivity).where(
                CardioActivity.user_id == conn.user_id,
                CardioActivity.source == "withings",
                CardioActivity.external_id == fields["external_id"],
            )
        )
        if existing is not None:
            for key, value in fields.items():
                setattr(existing, key, value)
        else:
            db.add(
                CardioActivity(user_id=conn.user_id, source="withings", **fields)
            )

    steps = await withings.fetch_daily_steps(conn, db, days_back=days_back)
    for s in steps:
        await db.merge(
            BodyMetric(
                user_id=conn.user_id,
                metric="steps",
                measured_at=s["measured_at"],
                source="withings",
                value=s["value"],
            )
        )
    await db.commit()
    return {"workouts": len(workouts), "step_days": len(steps)}


@router.post("/withings")
async def withings_event(
    userid: str = Form(...),
    startdate: int | None = Form(None),
    enddate: int | None = Form(None),
    appli: int | None = Form(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    conn = await db.scalar(
        select(OAuthConnection).where(
            OAuthConnection.provider == "withings",
            OAuthConnection.external_user_id == str(userid),
        )
    )
    if conn is None:
        return {"ok": True, "ignored": True}

    # appli 16 = aktivitet (pass + steg); övriga = kroppsmätningar
    if appli == 16:
        counts = await _sync_withings_workouts_and_steps(conn, db)
        return {"ok": True, **counts}

    measures = await withings.fetch_measures(conn, db, startdate, enddate)
    for m in measures:
        await db.merge(
            BodyMetric(
                user_id=conn.user_id,
                metric=m["metric"],
                measured_at=m["measured_at"],
                source="withings",
                value=m["value"],
            )
        )
    await db.commit()
    return {"ok": True, "measures": len(measures)}


# ── Apple Health (Health Auto Export) ─────────────────────────


@router.post("/apple-health")
async def apple_health_ingest(
    payload: dict,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Bearer-token saknas.")
    token = authorization.split(" ", 1)[1].strip()

    ingest_token = await db.scalar(
        select(IngestToken).where(IngestToken.token_hash == hash_token(token))
    )
    if ingest_token is None:
        raise HTTPException(401, "Ogiltig token.")

    user = await db.get(User, ingest_token.user_id)
    if user is None:
        raise HTTPException(401, "Ogiltig token.")

    counts = await apple_health.ingest(user, payload, db)
    ingest_token.last_seen_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True, **counts}
