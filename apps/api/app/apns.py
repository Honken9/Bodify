"""APNs-utskick till iOS-appen — token-baserad auth med .p8-nyckeln.

JWT:n signeras med ES256 och återanvänds i ~45 minuter (Apple vill ha
20–60 min). Ogiltiga enhetstokens (410/BadDeviceToken) rensas ur
databasen automatiskt. Utan konfiguration är allt en tyst no-op.
"""

import logging
import time
import uuid
from pathlib import Path

import httpx
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import ApnsToken

logger = logging.getLogger(__name__)

APNS_HOST = "https://api.push.apple.com"

_jwt_cache: dict = {"token": None, "issued": 0.0}


def _auth_jwt() -> str | None:
    settings = get_settings()
    if not (settings.apns_key_path and settings.apns_key_id and settings.apns_team_id):
        return None
    now = time.time()
    if _jwt_cache["token"] and now - _jwt_cache["issued"] < 45 * 60:
        return _jwt_cache["token"]
    try:
        key = Path(settings.apns_key_path).read_text()
    except OSError:
        logger.warning("APNs: kunde inte läsa nyckeln %s", settings.apns_key_path)
        return None
    token = jwt.encode(
        {"iss": settings.apns_team_id, "iat": int(now)},
        key,
        algorithm="ES256",
        headers={"kid": settings.apns_key_id},
    )
    _jwt_cache["token"] = token
    _jwt_cache["issued"] = now
    return token


async def send_to_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    title: str,
    body: str,
    url: str = "/",
) -> int:
    """Skicka till användarens alla iOS-enheter. Returnerar antal skickade."""
    auth = _auth_jwt()
    if auth is None:
        return 0

    tokens = list(
        await db.scalars(select(ApnsToken).where(ApnsToken.user_id == user_id))
    )
    if not tokens:
        return 0

    settings = get_settings()
    payload = {
        "aps": {
            "alert": {"title": title, "body": body},
            "sound": "default",
        },
        "url": url,
    }
    sent = 0
    dead: list[ApnsToken] = []
    try:
        async with httpx.AsyncClient(http2=True, timeout=10) as client:
            for device in tokens:
                try:
                    response = await client.post(
                        f"{APNS_HOST}/3/device/{device.token}",
                        json=payload,
                        headers={
                            "authorization": f"bearer {auth}",
                            "apns-topic": settings.apns_bundle_id,
                            "apns-push-type": "alert",
                            "apns-priority": "10",
                        },
                    )
                except httpx.HTTPError as exc:
                    logger.warning("APNs: nätverksfel: %s", exc)
                    continue
                if response.status_code == 200:
                    sent += 1
                elif response.status_code in (400, 410):
                    reason = ""
                    try:
                        reason = response.json().get("reason", "")
                    except ValueError:
                        pass
                    if reason in ("BadDeviceToken", "Unregistered", "ExpiredToken"):
                        dead.append(device)
                    else:
                        logger.warning("APNs: %s (%s)", reason, response.status_code)
                else:
                    logger.warning("APNs: oväntat svar %s", response.status_code)
    except ImportError:
        logger.warning("APNs: http2-stöd saknas (h2 ej installerat).")
        return 0

    for device in dead:
        await db.delete(device)
    if dead:
        await db.commit()
        logger.info("APNs: %s döda tokens rensade.", len(dead))
    return sent
