"""Withings: OAuth2, notify-prenumerationer och mätvärdeshämtning.

Withings pushar bara *att* något hänt (userid + tidsintervall) — själva
värdena hämtas via /measure och normaliseras till body_metrics.
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

AUTH_URL = "https://account.withings.com/oauth2_user/authorize2"
API_URL = "https://wbsapi.withings.net"

# Withings meastype → vårt metric-namn
MEASTYPE_MAP = {
    1: "weight",
    6: "fat_percent",
    76: "muscle_mass",
    77: "hydration",
    88: "bone_mass",
    91: "pwv",
    11: "resting_hr",
    9: "diastolic_bp",
    10: "systolic_bp",
}


def authorize_url(state: str) -> str:
    settings = get_settings()
    params = {
        "response_type": "code",
        "client_id": settings.withings_client_id,
        "scope": "user.metrics",
        "redirect_uri": f"{settings.public_base_url}/api/integrations/withings/callback",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


async def _token_request(data: dict) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(f"{API_URL}/v2/oauth2", data=data)
    resp.raise_for_status()
    body = resp.json()
    if body.get("status") != 0:
        raise RuntimeError(f"Withings-fel: {body}")
    return body["body"]


async def exchange_code(code: str) -> dict:
    settings = get_settings()
    return await _token_request(
        {
            "action": "requesttoken",
            "grant_type": "authorization_code",
            "client_id": settings.withings_client_id,
            "client_secret": settings.withings_client_secret,
            "code": code,
            "redirect_uri": f"{settings.public_base_url}/api/integrations/withings/callback",
        }
    )


async def _refresh(conn: OAuthConnection, db: AsyncSession) -> None:
    settings = get_settings()
    body = await _token_request(
        {
            "action": "requesttoken",
            "grant_type": "refresh_token",
            "client_id": settings.withings_client_id,
            "client_secret": settings.withings_client_secret,
            "refresh_token": decrypt(conn.refresh_token_enc),
        }
    )
    conn.access_token_enc = encrypt(body["access_token"])
    conn.refresh_token_enc = encrypt(body["refresh_token"])
    conn.expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=int(body.get("expires_in", 10800))
    )
    await db.commit()


async def get_access_token(conn: OAuthConnection, db: AsyncSession) -> str:
    if conn.expires_at and conn.expires_at < datetime.now(timezone.utc) + timedelta(
        minutes=5
    ):
        await _refresh(conn, db)
    return decrypt(conn.access_token_enc)


async def subscribe_notifications(conn: OAuthConnection, db: AsyncSession) -> None:
    """Prenumerera på notiser: appli 1 = kroppsmätningar, 4 = hjärta/blodtryck."""
    settings = get_settings()
    token = await get_access_token(conn, db)
    callback = f"{settings.public_base_url}/api/webhooks/withings"
    async with httpx.AsyncClient(timeout=15) as client:
        for appli in (1, 4):
            resp = await client.post(
                f"{API_URL}/notify",
                headers={"Authorization": f"Bearer {token}"},
                data={"action": "subscribe", "callbackurl": callback, "appli": appli},
            )
            body = resp.json()
            if body.get("status") != 0:
                logger.warning("Withings-prenumeration appli=%s: %s", appli, body)


async def fetch_measures(
    conn: OAuthConnection,
    db: AsyncSession,
    startdate: int | None = None,
    enddate: int | None = None,
) -> list[dict]:
    """Hämta mätningar. Returnerar [{metric, measured_at, value}, ...]."""
    token = await get_access_token(conn, db)
    data = {
        "action": "getmeas",
        "meastypes": ",".join(str(t) for t in MEASTYPE_MAP),
        "category": 1,
    }
    if startdate:
        data["startdate"] = startdate
    if enddate:
        data["enddate"] = enddate

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{API_URL}/measure",
            headers={"Authorization": f"Bearer {token}"},
            data=data,
        )
    resp.raise_for_status()
    body = resp.json()
    if body.get("status") != 0:
        raise RuntimeError(f"Withings-fel: {body}")

    results = []
    for group in body["body"].get("measuregrps", []):
        measured_at = datetime.fromtimestamp(group["date"], tz=timezone.utc)
        for measure in group.get("measures", []):
            metric = MEASTYPE_MAP.get(measure["type"])
            if metric is None:
                continue
            value = measure["value"] * (10 ** measure["unit"])
            results.append(
                {
                    "metric": metric,
                    "measured_at": measured_at,
                    "value": round(value, 3),
                }
            )
    return results
