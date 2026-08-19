"""Inkommande webhooks — undantagna från Cloudflare Access men skyddade
med egna hemligheter (Strava verify-token, Withings-koppling via userid,
Apple Health via personlig Bearer-token)."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.integrations import apple_health, cloudflare, strava, withings
from app.integrations.cloudflare import CloudflareError
from app.models import (
    BodyMetric,
    CardioActivity,
    Club,
    ClubMember,
    IngestToken,
    OAuthConnection,
    User,
)
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
    # Klockans GPS-lösa kopia av samma pass ska bort — Strava vinner
    from app.services.strava_sync import remove_non_strava_duplicates

    await remove_non_strava_duplicates(
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
        db.add(CardioActivity(user_id=conn.user_id, source="strava", **fields))
    await db.commit()

    from app.services.watch_link import autolink_watch_activities

    user = await db.get(User, conn.user_id)
    if user is not None:
        await autolink_watch_activities(db, user)
    return {"ok": True}


# ── Withings ──────────────────────────────────────────────────


@router.head("/withings")
async def withings_head() -> PlainTextResponse:
    """Withings validerar callback-URL:en med en HEAD-request."""
    return PlainTextResponse("")


async def _sync_withings_workouts_and_steps(
    conn: OAuthConnection, db: AsyncSession, days_back: int = 7
) -> dict:
    """Hämta träningspass + daglig stegräkning och upserta idempotent.

    Pass som redan finns via Strava (samma typ, start inom ±20 min)
    hoppas över — Strava-versionen har GPS och rikast data."""
    from app.services.strava_sync import DUP_WINDOW

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
            continue
        strava_twin = await db.scalar(
            select(CardioActivity).where(
                CardioActivity.user_id == conn.user_id,
                CardioActivity.source == "strava",
                CardioActivity.type == fields["type"],
                CardioActivity.started_at >= fields["started_at"] - DUP_WINDOW,
                CardioActivity.started_at <= fields["started_at"] + DUP_WINDOW,
            )
        )
        if strava_twin is not None:
            continue
        db.add(
            CardioActivity(user_id=conn.user_id, source="withings", **fields)
        )

    days = await withings.fetch_daily_activity(conn, db, days_back=days_back)
    day_metrics = {
        "steps": "steps",
        "hr_average": "hr_avg",
        "hr_min": "hr_min",
        "hr_max": "hr_max",
    }
    for d in days:
        for field, metric in day_metrics.items():
            if d.get(field) is None:
                continue
            await db.merge(
                BodyMetric(
                    user_id=conn.user_id,
                    metric=metric,
                    measured_at=d["measured_at"],
                    source="withings",
                    value=d[field],
                )
            )
    await db.commit()

    # Slå ihop klockans gympass med Shapiqo-loggade styrkepass
    from app.services.watch_link import autolink_watch_activities

    user = await db.get(User, conn.user_id)
    if user is not None:
        await autolink_watch_activities(db, user)
    return {"workouts": len(workouts), "step_days": len(days)}


async def _sync_withings_sleep(
    conn: OAuthConnection, db: AsyncSession, days_back: int = 7
) -> dict:
    """Nattsömn → SleepSession (readiness-coachen) + sömngrafer i Hälsa."""
    from app.models import SleepSession

    nights = await withings.fetch_sleep(conn, db, days_back=days_back)
    for n in nights:
        existing = await db.scalar(
            select(SleepSession).where(
                SleepSession.user_id == conn.user_id,
                SleepSession.start_at == n["start_at"],
                SleepSession.source == "withings",
            )
        )
        if existing is not None:
            existing.end_at = n["end_at"]
            existing.deep_s = n["deep_s"]
            existing.rem_s = n["rem_s"]
            existing.light_s = n["light_s"]
            existing.awake_s = n["awake_s"]
        else:
            db.add(
                SleepSession(
                    user_id=conn.user_id,
                    start_at=n["start_at"],
                    end_at=n["end_at"],
                    deep_s=n["deep_s"],
                    rem_s=n["rem_s"],
                    light_s=n["light_s"],
                    awake_s=n["awake_s"],
                    source="withings",
                )
            )
        # Grafvänliga mätetal — dagstämplas på uppvakningsmorgonen
        morning = n["end_at"].replace(hour=0, minute=0, second=0, microsecond=0)
        await db.merge(
            BodyMetric(
                user_id=conn.user_id,
                metric="sleep_duration",
                measured_at=morning,
                source="withings",
                value=round(n["total_s"] / 3600, 2),
            )
        )
        if n["score"] is not None:
            await db.merge(
                BodyMetric(
                    user_id=conn.user_id,
                    metric="sleep_score",
                    measured_at=morning,
                    source="withings",
                    value=float(n["score"]),
                )
            )
    await db.commit()
    return {"sleep_nights": len(nights)}


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

    # appli 16 = aktivitet (pass + steg), 44 = sömn; övriga = kroppsmätningar
    if appli == 16:
        counts = await _sync_withings_workouts_and_steps(conn, db)
        return {"ok": True, **counts}
    if appli == 44:
        counts = await _sync_withings_sleep(conn, db)
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


@router.get("/apple-health")
async def apple_health_ping() -> dict:
    """HAE provtrycker URL:en med GET före export — svara vänligt
    istället för 405 så appens anslutningstest inte ser trasigt ut."""
    return {
        "ok": True,
        "hint": "Skicka exporten som POST med headern Authorization: Bearer <token>.",
    }


@router.post("/apple-health")
async def apple_health_ingest(
    payload: dict,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_session),
) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        # Skriv ut vad som faktiskt kom (utan värden) — skiljer "glömt
        # headern" från "fel format" vid felsökning i loggen
        logger.warning(
            "Apple Health-ingest nekad: Authorization-header %s.",
            "saknas" if not authorization else "har fel format (börjar inte med 'Bearer ')",
        )
        raise HTTPException(401, "Bearer-token saknas.")
    token = authorization.split(" ", 1)[1].strip()

    ingest_token = await db.scalar(
        select(IngestToken).where(IngestToken.token_hash == hash_token(token))
    )
    if ingest_token is None:
        logger.warning(
            "Apple Health-ingest nekad: token matchar ingen registrerad "
            "(fel token eller extra tecken från kopieringen)."
        )
        raise HTTPException(401, "Ogiltig token.")

    user = await db.get(User, ingest_token.user_id)
    if user is None:
        raise HTTPException(401, "Ogiltig token.")

    counts = await apple_health.ingest(user, payload, db)
    ingest_token.last_seen_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True, **counts}


# ── Självregistrering med inbjudningskod ─────────────────────
# Publik (Access-undantagen) men kräver giltig kod: en ligas
# inbjudningskod eller den globala SIGNUP_CODE. Vitlistar i Cloudflare
# och skapar kontot — ligakod ger dessutom medlemskap direkt.

_signup_hits: dict[str, list[float]] = {}


class SignupIn(BaseModel):
    email: str = Field(max_length=320)
    display_name: str | None = Field(default=None, max_length=120)
    code: str = Field(min_length=4, max_length=16)


@router.post("/signup", status_code=201)
async def signup(
    payload: SignupIn,
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> dict:
    import time as _time

    ip = request.client.host if request.client else "?"
    now = _time.monotonic()
    hits = [t for t in _signup_hits.get(ip, []) if now - t < 3600]
    if len(hits) >= 5:
        raise HTTPException(429, "För många försök — vänta en stund.")
    hits.append(now)
    if len(_signup_hits) > 10_000:
        _signup_hits.clear()
    _signup_hits[ip] = hits

    email = payload.email.lower().strip()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(400, "Ogiltig e-postadress.")

    code = payload.code.upper().strip()
    club = await db.scalar(select(Club).where(Club.invite_code == code))
    settings = get_settings()
    global_ok = bool(settings.signup_code) and code == settings.signup_code.upper()
    if club is None and not global_ok:
        raise HTTPException(404, "Ogiltig inbjudningskod.")

    user = await db.scalar(select(User).where(User.email == email))
    created = False
    if user is None:
        user = User(
            email=email,
            display_name=(payload.display_name or "").strip() or None,
        )
        db.add(user)
        await db.flush()
        created = True

    joined_club = None
    if club is not None:
        member = await db.scalar(
            select(ClubMember).where(
                ClubMember.club_id == club.id, ClubMember.user_id == user.id
            )
        )
        if member is None:
            club.members.append(ClubMember(user_id=user.id))
        joined_club = club.name
    await db.commit()

    whitelisted = False
    if cloudflare.is_configured():
        try:
            await cloudflare.add_email(email)
            whitelisted = True
        except CloudflareError:
            logger.warning("Signup: kunde inte vitlista %s i Cloudflare.", email)

    if created:
        from app import push

        admins = await db.scalars(select(User).where(User.is_admin.is_(True)))
        for admin_user in admins:
            await push.send_to_user(
                db,
                admin_user.id,
                "🆕 Ny användare",
                f"{email} registrerade sig"
                + (f" via ligan {joined_club}" if joined_club else "")
                + ".",
                url="/admin",
            )

    return {
        "ok": True,
        "created": created,
        "whitelisted": whitelisted,
        "club": joined_club,
    }
