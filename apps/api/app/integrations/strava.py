"""Strava: OAuth2, tokenhantering och aktivitetshämtning.

Flöde: användaren kopplar via OAuth → en app-global webhook-prenumeration
notifierar om nya aktiviteter → vi hämtar detaljerna och normaliserar in i
cardio_activities.
"""

import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import OAuthConnection
from app.security import decrypt, encrypt

logger = logging.getLogger(__name__)

AUTH_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"
API_URL = "https://www.strava.com/api/v3"

TYPE_MAP = {
    "Run": "run",
    "TrailRun": "run",
    "VirtualRun": "run",
    "Ride": "ride",
    "VirtualRide": "ride",
    "MountainBikeRide": "ride",
    "Walk": "walk",
    "Hike": "walk",
    "Swim": "swim",
}


def authorize_url(state: str) -> str:
    settings = get_settings()
    params = {
        "client_id": settings.strava_client_id,
        "redirect_uri": f"{settings.public_base_url}/api/integrations/strava/callback",
        "response_type": "code",
        "scope": "activity:read_all",
        "state": state,
        "approval_prompt": "auto",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> dict:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "client_id": settings.strava_client_id,
                "client_secret": settings.strava_client_secret,
                "code": code,
                "grant_type": "authorization_code",
            },
        )
    resp.raise_for_status()
    return resp.json()


async def _refresh(conn: OAuthConnection, db: AsyncSession) -> None:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "client_id": settings.strava_client_id,
                "client_secret": settings.strava_client_secret,
                "grant_type": "refresh_token",
                "refresh_token": decrypt(conn.refresh_token_enc),
            },
        )
    resp.raise_for_status()
    data = resp.json()
    conn.access_token_enc = encrypt(data["access_token"])
    conn.refresh_token_enc = encrypt(data["refresh_token"])
    conn.expires_at = datetime.fromtimestamp(data["expires_at"], tz=timezone.utc)
    await db.commit()


async def get_access_token(conn: OAuthConnection, db: AsyncSession) -> str:
    if conn.expires_at and conn.expires_at < datetime.now(timezone.utc) + timedelta(
        minutes=5
    ):
        await _refresh(conn, db)
    return decrypt(conn.access_token_enc)


async def fetch_activity(
    conn: OAuthConnection, db: AsyncSession, activity_id: str
) -> dict | None:
    token = await get_access_token(conn, db)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{API_URL}/activities/{activity_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def normalize_activity(activity: dict) -> dict:
    """Strava-aktivitet → fält för cardio_activities."""
    distance_m = float(activity.get("distance") or 0)
    moving_s = int(activity.get("moving_time") or 0)
    pace = round(moving_s / (distance_m / 1000), 1) if distance_m > 100 else None
    return {
        "type": TYPE_MAP.get(activity.get("sport_type") or activity.get("type"), "other"),
        "external_id": str(activity["id"]),
        "name": (activity.get("name") or "")[:200] or None,
        "started_at": datetime.fromisoformat(
            activity["start_date"].replace("Z", "+00:00")
        ),
        "duration_s": moving_s,
        "distance_m": distance_m or None,
        "avg_hr": activity.get("average_heartrate"),
        "max_hr": activity.get("max_heartrate"),
        "avg_pace_s_per_km": pace,
        "calories": activity.get("calories") or activity.get("kilojoules"),
        "raw": {
            "sport_type": activity.get("sport_type"),
            "elapsed_time": activity.get("elapsed_time"),
            "total_elevation_gain": activity.get("total_elevation_gain"),
            # GPS för träningskartan: rutt (kodad polyline) + startpunkt
            "polyline": (activity.get("map") or {}).get("polyline")
            or (activity.get("map") or {}).get("summary_polyline"),
            "start_latlng": activity.get("start_latlng"),
        },
    }
