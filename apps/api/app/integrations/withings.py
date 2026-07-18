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

# user.metrics = kroppsmätningar, user.activity = träningspass/aktivitet
SCOPES = "user.metrics,user.activity"

# Withings workout-kategori → (vår typ, svenskt namn)
WORKOUT_CATEGORIES: dict[int, tuple[str, str]] = {
    1: ("walk", "Promenad"),
    2: ("run", "Löpning"),
    3: ("walk", "Vandring"),
    6: ("ride", "Cykling"),
    7: ("swim", "Simning"),
    12: ("other", "Tennis"),
    14: ("other", "Squash"),
    15: ("other", "Badminton"),
    16: ("other", "Styrketräning"),
    17: ("other", "Kroppsviktsträning"),
    18: ("other", "Crosstrainer"),
    19: ("other", "Pilates"),
    20: ("other", "Basket"),
    21: ("other", "Fotboll"),
    27: ("other", "Golf"),
    28: ("other", "Yoga"),
    29: ("other", "Dans"),
    30: ("other", "Boxning"),
    33: ("other", "Kampsport"),
    34: ("other", "Skidåkning"),
    35: ("other", "Snowboard"),
    187: ("other", "Rodd"),
    188: ("other", "Zumba"),
    192: ("other", "Handboll"),
    194: ("other", "Ishockey"),
    195: ("other", "Klättring"),
    306: ("walk", "Promenad (inomhus)"),
    307: ("run", "Löpband"),
    308: ("ride", "Spinning"),
}


def authorize_url(state: str) -> str:
    settings = get_settings()
    params = {
        "response_type": "code",
        "client_id": settings.withings_client_id,
        "scope": SCOPES,
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
    """Prenumerera på notiser: appli 1 = kroppsmätningar, 4 = hjärta/blodtryck,
    16 = aktivitet/träningspass."""
    settings = get_settings()
    token = await get_access_token(conn, db)
    callback = f"{settings.public_base_url}/api/webhooks/withings"
    async with httpx.AsyncClient(timeout=15) as client:
        for appli in (1, 4, 16):
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


async def _api_post(token: str, path: str, data: dict) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{API_URL}{path}",
            headers={"Authorization": f"Bearer {token}"},
            data=data,
        )
    resp.raise_for_status()
    body = resp.json()
    if body.get("status") != 0:
        raise RuntimeError(f"Withings-fel: {body}")
    return body["body"]


def normalize_workouts(series: list[dict]) -> list[dict]:
    """Withings getworkouts-serie → fält för CardioActivity."""
    results = []
    for w in series:
        wtype, name = WORKOUT_CATEGORIES.get(
            int(w.get("category", 0)), ("other", "Träning")
        )
        start = int(w["startdate"])
        duration = max(int(w["enddate"]) - start, 0)
        data = w.get("data", {}) or {}
        distance = data.get("distance") or None
        pace = (
            round(duration / (float(distance) / 1000), 1)
            if distance and float(distance) > 100 and duration
            else None
        )
        results.append(
            {
                "external_id": str(w["id"]),
                "type": wtype,
                "name": name,
                "started_at": datetime.fromtimestamp(start, tz=timezone.utc),
                "duration_s": duration,
                "distance_m": float(distance) if distance else None,
                "calories": data.get("calories") or None,
                "avg_hr": data.get("hr_average") or None,
                "max_hr": data.get("hr_max") or None,
                "avg_pace_s_per_km": pace,
            }
        )
    return results


async def fetch_workouts(
    conn: OAuthConnection,
    db: AsyncSession,
    days_back: int = 90,
) -> list[dict]:
    """Hämta träningspass (kräver user.activity-scope)."""
    token = await get_access_token(conn, db)
    today = datetime.now(timezone.utc).date()
    body = await _api_post(
        token,
        "/v2/measure",
        {
            "action": "getworkouts",
            "startdateymd": (today - timedelta(days=days_back)).isoformat(),
            "enddateymd": today.isoformat(),
            "data_fields": "calories,distance,hr_average,hr_max,steps",
        },
    )
    return normalize_workouts(body.get("series", []))


async def fetch_daily_steps(
    conn: OAuthConnection,
    db: AsyncSession,
    days_back: int = 90,
) -> list[dict]:
    """Daglig stegräkning → [{measured_at, value}, ...] för metric 'steps'."""
    token = await get_access_token(conn, db)
    today = datetime.now(timezone.utc).date()
    body = await _api_post(
        token,
        "/v2/measure",
        {
            "action": "getactivity",
            "startdateymd": (today - timedelta(days=days_back)).isoformat(),
            "enddateymd": today.isoformat(),
            "data_fields": "steps",
        },
    )
    results = []
    for day in body.get("activities", []):
        steps = day.get("steps")
        if steps is None:
            continue
        results.append(
            {
                "measured_at": datetime.fromisoformat(day["date"]).replace(
                    tzinfo=timezone.utc
                ),
                "value": float(steps),
            }
        )
    return results
