"""Autentisering via Cloudflare Access.

Appen har inga egna lösenord. Cloudflare Access sköter inloggning och
injicerar en signerad JWT i headern `Cf-Access-Jwt-Assertion` på varje
request. Här verifieras signatur, audience och issuer kryptografiskt —
vi litar aldrig blint på att trafiken kom via tunneln.
"""

import logging
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, Request
from jwt import PyJWKClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import User

logger = logging.getLogger(__name__)

ACCESS_JWT_HEADER = "Cf-Access-Jwt-Assertion"
ACCESS_JWT_COOKIE = "CF_Authorization"


@lru_cache
def _jwks_client() -> PyJWKClient:
    team_domain = get_settings().cf_team_domain
    return PyJWKClient(
        f"https://{team_domain}/cdn-cgi/access/certs", cache_keys=True
    )


def decode_access_token(token: str) -> dict:
    """Verifiera en Cloudflare Access-JWT och returnera dess claims."""
    settings = get_settings()
    signing_key = _jwks_client().get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=settings.cf_access_aud,
        issuer=f"https://{settings.cf_team_domain}",
    )


def _authenticated_email(request: Request) -> str:
    settings = get_settings()

    if settings.dev_auth_email:
        # Lokal utveckling utan Cloudflare framför sig.
        return settings.dev_auth_email.lower()

    token = request.headers.get(ACCESS_JWT_HEADER) or request.cookies.get(
        ACCESS_JWT_COOKIE
    )
    if not token:
        raise HTTPException(401, "Cloudflare Access-token saknas.")

    try:
        claims = decode_access_token(token)
    except jwt.PyJWTError as exc:
        logger.warning("Ogiltig Access-token: %s", exc)
        raise HTTPException(401, "Ogiltig Cloudflare Access-token.") from exc

    email = claims.get("email")
    if not email:
        # T.ex. service-tokens saknar e-post; de får inte agera användare.
        raise HTTPException(401, "Access-token saknar e-postclaim.")
    return email.lower()


async def get_current_user(
    request: Request, session: AsyncSession = Depends(get_session)
) -> User:
    email = _authenticated_email(request)
    settings = get_settings()

    user = await session.scalar(select(User).where(User.email == email))
    if user is None:
        if (
            settings.bootstrap_admin_email
            and email == settings.bootstrap_admin_email.lower()
        ):
            user = User(email=email, is_admin=True)
        elif settings.auto_provision_users:
            user = User(email=email)
        else:
            raise HTTPException(
                403, "Din e-postadress är inte upplagd i Bodify ännu."
            )
        session.add(user)
        try:
            await session.commit()
            await session.refresh(user)
        except IntegrityError:
            # Två parallella förstaanrop kan försöka skapa samma användare —
            # den som förlorade racet läser upp den som vann.
            await session.rollback()
            user = await session.scalar(select(User).where(User.email == email))
            if user is None:  # bör inte hända
                raise HTTPException(500, "Kunde inte skapa användaren.")

    # RLS-nyckeln: all användardata filtreras på detta värde i databasen.
    if session.bind.dialect.name == "postgresql":
        await session.execute(
            select(func.set_config("app.user_id", str(user.id), True))
        )

    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "Kräver adminbehörighet.")
    return user
