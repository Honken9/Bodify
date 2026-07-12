"""Web Push-utskick (VAPID) via pywebpush.

Självhostat — inga externa konton krävs utöver VAPID-nyckelparet.
Prenumerationer som inte längre är giltiga (410/404) rensas automatiskt.
"""

import json
import logging
import uuid

from pywebpush import WebPushException, webpush
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import PushSubscription

logger = logging.getLogger(__name__)


async def send_to_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    title: str,
    body: str,
    url: str = "/",
) -> int:
    """Skicka en push-notis till användarens alla enheter. Returnerar antal."""
    settings = get_settings()
    if not settings.vapid_private_key:
        logger.debug("VAPID-nycklar saknas — hoppar över push.")
        return 0

    subscriptions = list(
        await db.scalars(
            select(PushSubscription).where(PushSubscription.user_id == user_id)
        )
    )
    sent = 0
    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=json.dumps({"title": title, "body": body, "url": url}),
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_subject},
            )
            sent += 1
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            if status in (404, 410):
                await db.delete(sub)  # enheten har avregistrerat sig
            else:
                logger.warning("Push misslyckades: %s", exc)
    await db.commit()
    return sent
