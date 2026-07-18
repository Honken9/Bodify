import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_session
from app.models import CardioActivity, User

router = APIRouter(prefix="/api/cardio", tags=["cardio"])


class CardioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    source: str
    name: str | None
    started_at: datetime
    duration_s: int
    distance_m: float | None
    avg_hr: float | None
    max_hr: float | None
    avg_pace_s_per_km: float | None
    calories: float | None


class CardioCreate(BaseModel):
    type: str = Field(pattern="^(run|ride|walk|swim|other)$")
    name: str | None = Field(default=None, max_length=200)
    started_at: datetime
    duration_s: int = Field(gt=0, le=86400)
    distance_m: float | None = Field(default=None, gt=0, le=1_000_000)
    avg_hr: float | None = Field(default=None, gt=0, le=250)


class CardioGeoOut(BaseModel):
    """Aktivitet med GPS-data för träningskartan — rutt (kodad polyline)
    för t.ex. löprundor, eller bara startpunkt för platsbundna pass."""

    id: uuid.UUID
    type: str
    name: str | None
    started_at: datetime
    duration_s: int
    distance_m: float | None
    polyline: str | None
    start: list[float] | None


@router.get("/geo", response_model=list[CardioGeoOut])
async def list_geo_activities(
    limit: int = 1000,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[CardioGeoOut]:
    rows = await db.scalars(
        select(CardioActivity)
        .where(
            CardioActivity.user_id == user.id,
            CardioActivity.linked_session_id.is_(None),
        )
        .order_by(CardioActivity.started_at.desc())
        .limit(min(limit, 5000))
    )
    result = []
    for a in rows:
        raw = a.raw or {}
        polyline = raw.get("polyline") or None
        start = raw.get("start_latlng") or None
        if not polyline and not (isinstance(start, list) and len(start) == 2):
            continue  # ingen GPS-data — hör inte hemma på kartan
        result.append(
            CardioGeoOut(
                id=a.id,
                type=a.type,
                name=a.name,
                started_at=a.started_at,
                duration_s=a.duration_s,
                distance_m=float(a.distance_m) if a.distance_m else None,
                polyline=polyline,
                start=start if isinstance(start, list) and len(start) == 2 else None,
            )
        )

    # Shapiqo-loggade styrkepass med position — gymmet syns på kartan
    from app.models import WorkoutSession

    sessions = await db.scalars(
        select(WorkoutSession).where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.start_lat.is_not(None),
            WorkoutSession.start_lng.is_not(None),
        )
    )
    for ws in sessions:
        duration = 0
        if ws.finished_at is not None:
            duration = max(int((ws.finished_at - ws.started_at).total_seconds()), 0)
        result.append(
            CardioGeoOut(
                id=ws.id,
                type="strength",
                name=ws.program_day.name if ws.program_day else "Styrkepass",
                started_at=ws.started_at,
                duration_s=duration,
                distance_m=None,
                polyline=None,
                start=[float(ws.start_lat), float(ws.start_lng)],
            )
        )
    return result


class PlaceOut(BaseModel):
    name: str
    lat: float
    lng: float


# Nominatims användarvillkor: max 1 anrop/sekund — enkel broms per användare
_geo_search_last: dict[str, float] = {}


@router.get("/geo-search", response_model=list[PlaceOut])
async def geo_search(
    q: str,
    user: User = Depends(get_current_user),
) -> list[PlaceOut]:
    """Sök plats via OpenStreetMap/Nominatim (t.ex. "SATS Farsta") —
    gratis och nyckellöst, i linje med kartan i övrigt."""
    q = q.strip()[:200]
    if len(q) < 2:
        return []
    import time

    now = time.monotonic()
    last = _geo_search_last.get(str(user.id), 0.0)
    if now - last < 1.0:
        raise HTTPException(429, "Sök lite långsammare — max en sökning per sekund.")
    if len(_geo_search_last) > 10_000:
        _geo_search_last.clear()
    _geo_search_last[str(user.id)] = now
    import httpx

    try:
        async with httpx.AsyncClient(
            timeout=10,
            headers={"User-Agent": "Shapiqo/1.0 (self-hosted fitness app)"},
        ) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": q,
                    "format": "jsonv2",
                    "limit": 6,
                    "accept-language": "sv",
                },
            )
        resp.raise_for_status()
        rows = resp.json()
    except httpx.HTTPError:
        raise HTTPException(502, "Platssökningen svarar inte — försök igen.")
    return [
        PlaceOut(
            name=(row.get("display_name") or "")[:160],
            lat=float(row["lat"]),
            lng=float(row["lon"]),
        )
        for row in rows
        if row.get("lat") and row.get("lon")
    ]


@router.get("", response_model=list[CardioOut])
async def list_activities(
    limit: int = 30,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[CardioActivity]:
    rows = await db.scalars(
        select(CardioActivity)
        .where(
            CardioActivity.user_id == user.id,
            CardioActivity.linked_session_id.is_(None),
        )
        .order_by(CardioActivity.started_at.desc())
        .limit(min(limit, 5000))
        .offset(offset)
    )
    return list(rows)


@router.post("", response_model=CardioOut, status_code=201)
async def add_activity(
    payload: CardioCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> CardioActivity:
    pace = (
        round(payload.duration_s / (payload.distance_m / 1000), 1)
        if payload.distance_m and payload.distance_m > 100
        else None
    )
    activity = CardioActivity(
        user_id=user.id,
        source="manual",
        external_id=None,
        type=payload.type,
        name=payload.name,
        started_at=payload.started_at,
        duration_s=payload.duration_s,
        distance_m=payload.distance_m,
        avg_hr=payload.avg_hr,
        avg_pace_s_per_km=pace,
    )
    db.add(activity)
    await db.commit()
    await db.refresh(activity)
    return activity


class CardioDetailOut(CardioOut):
    """Full passvy: allt vi vet om aktiviteten, inkl. Strava-extras."""

    source: str
    polyline: str | None = None
    start: list[float] | None = None
    extras: dict = {}
    splits: list[dict] = []


async def _enrich_from_strava(
    activity: CardioActivity, user: User, db: AsyncSession
) -> None:
    """Backfillen ger bara summeringar — km-varv (splits) finns i
    detaljsvaret. Hämtas en gång när passet öppnas och cacheas i raw."""
    from app.integrations import strava
    from app.models import OAuthConnection

    conn = await db.scalar(
        select(OAuthConnection).where(
            OAuthConnection.user_id == user.id,
            OAuthConnection.provider == "strava",
        )
    )
    if conn is None or not activity.external_id:
        return
    try:
        detail = await strava.fetch_activity(conn, db, activity.external_id)
    except Exception:
        return  # nätverksfel/kvot — visa det vi har, försök igen nästa gång
    if not detail:
        return
    fields = strava.normalize_activity(detail)
    merged = dict(activity.raw or {})
    for key, value in fields["raw"].items():
        if value is not None:
            merged[key] = value
    merged.setdefault("splits", [])  # markera som hämtat — ingen omhämtning
    activity.raw = merged
    if fields.get("calories"):
        activity.calories = fields["calories"]
    await db.commit()


@router.get("/{activity_id}", response_model=CardioDetailOut)
async def get_activity(
    activity_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> CardioDetailOut:
    activity = await db.get(CardioActivity, activity_id)
    if activity is None or activity.user_id != user.id:
        raise HTTPException(404, "Aktiviteten finns inte.")
    raw = activity.raw or {}
    if activity.source == "strava" and "splits" not in raw:
        await _enrich_from_strava(activity, user, db)
        raw = activity.raw or {}
    start = raw.get("start_latlng")
    extras = {
        key: value
        for key, value in raw.items()
        if key not in ("polyline", "start_latlng", "splits")
        and value not in (None, 0, "")
    }
    out = CardioDetailOut.model_validate(activity)
    out.polyline = raw.get("polyline") or None
    out.start = start if isinstance(start, list) and len(start) == 2 else None
    out.extras = extras
    out.splits = raw.get("splits") or []
    return out


class BulkLocationUpdate(BaseModel):
    """Platssätt flera pass i ett svep — valda id:n eller alla som saknar
    plats. Pass med GPS-rutt rörs aldrig."""

    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    ids: list[uuid.UUID] | None = Field(default=None, max_length=5000)
    all_missing: bool = False


@router.patch("/location-bulk")
async def set_location_bulk(
    payload: BulkLocationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    if not payload.all_missing and not payload.ids:
        raise HTTPException(400, "Ange pass-id:n eller all_missing.")
    stmt = select(CardioActivity).where(CardioActivity.user_id == user.id)
    if not payload.all_missing:
        stmt = stmt.where(CardioActivity.id.in_(payload.ids or []))
    updated = 0
    for activity in await db.scalars(stmt):
        raw = activity.raw or {}
        if raw.get("polyline"):
            continue  # riktig GPS-rutt vinner alltid
        if payload.all_missing and raw.get("start_latlng"):
            continue  # "alla som saknar" ska inte skriva över satta platser
        activity.raw = {
            **raw,
            "start_latlng": [payload.lat, payload.lng],
            "location_source": "manual",
        }
        updated += 1
    await db.commit()
    return {"ok": True, "updated": updated}


class LocationUpdate(BaseModel):
    """Manuell plats för pass utan GPS — så även gympass kan visas på
    kartan (Strava skickar bara position för GPS-inspelade pass)."""

    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


@router.patch("/{activity_id}/location", response_model=CardioDetailOut)
async def set_location(
    activity_id: uuid.UUID,
    payload: LocationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> CardioDetailOut:
    activity = await db.get(CardioActivity, activity_id)
    if activity is None or activity.user_id != user.id:
        raise HTTPException(404, "Aktiviteten finns inte.")
    activity.raw = {
        **(activity.raw or {}),
        "start_latlng": [payload.lat, payload.lng],
        "location_source": "manual",
    }
    await db.commit()
    await db.refresh(activity)
    return await get_activity(activity_id, user, db)


@router.delete("/{activity_id}", status_code=204)
async def delete_activity(
    activity_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    activity = await db.get(CardioActivity, activity_id)
    if activity is None or activity.user_id != user.id:
        raise HTTPException(404, "Aktiviteten finns inte.")
    await db.delete(activity)
    await db.commit()
