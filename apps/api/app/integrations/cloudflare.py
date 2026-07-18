"""Cloudflare Access-administration: hantera e-postvitlistan via API.

Låter admin bjuda in externa testare direkt från Bodify istället för att
logga in i Zero Trust-dashboarden. Kräver en API-token med behörigheten
"Access: Apps and Policies – Edit".
"""

import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

API = "https://api.cloudflare.com/client/v4"


class CloudflareNotConfigured(Exception):
    """API-token/konto-id/app-id saknas i miljön."""


class CloudflareError(Exception):
    """Cloudflare-API:t svarade med fel."""


def is_configured() -> bool:
    s = get_settings()
    return bool(s.cf_api_token and s.cf_account_id and s.cf_access_app_id)


def _require_config() -> None:
    if not is_configured():
        raise CloudflareNotConfigured(
            "Sätt CF_API_TOKEN, CF_ACCOUNT_ID och CF_ACCESS_APP_ID i .env."
        )


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=API,
        timeout=15,
        headers={"Authorization": f"Bearer {get_settings().cf_api_token}"},
    )


def _unwrap(resp: httpx.Response) -> dict | list:
    try:
        body = resp.json()
    except ValueError:
        logger.warning("Cloudflare-svar utan JSON (%s): %s", resp.status_code, resp.text[:300])
        raise CloudflareError(f"Cloudflare-fel: HTTP {resp.status_code}")
    if not body.get("success"):
        logger.warning("Cloudflare-fel (%s): %s", resp.status_code, body.get("errors"))
        raise CloudflareError(f"Cloudflare-fel: {body.get('errors')}")
    return body["result"]


def _account_policy_url(policy_id: str) -> str:
    """Kontonivå — för Cloudflares nya återanvändbara policies."""
    s = get_settings()
    return f"/accounts/{s.cf_account_id}/access/policies/{policy_id}"


def _app_policy_url(policy_id: str = "") -> str:
    """App-nivå — för äldre policies knutna direkt till applikationen."""
    s = get_settings()
    base = f"/accounts/{s.cf_account_id}/access/apps/{s.cf_access_app_id}/policies"
    return f"{base}/{policy_id}" if policy_id else base


def _is_reusable(policy: dict) -> bool:
    return bool(policy.get("reusable"))


async def _get_policy() -> dict:
    """Hämta policyn som bär e-postvitlistan.

    Nya Cloudflare-konton använder återanvändbara policies på kontonivå:
    app-listningen visar dem, men innehållet (include-listan) måste
    hämtas — och uppdateras — via kontonivå-API:t."""
    _require_config()
    s = get_settings()
    async with _client() as client:
        if s.cf_access_policy_id:
            # Prova kontonivå först, fall tillbaka till app-nivå
            resp = await client.get(_account_policy_url(s.cf_access_policy_id))
            if resp.status_code < 400 and resp.json().get("success"):
                policy = resp.json()["result"]
                policy["reusable"] = True
                return policy
            return _unwrap(await client.get(_app_policy_url(s.cf_access_policy_id)))

        policies = _unwrap(await client.get(_app_policy_url()))
        for policy in policies:
            if policy.get("decision") != "allow":
                continue
            if _is_reusable(policy):
                # Stub från app-listningen — hämta hela policyn på kontonivå
                full = _unwrap(await client.get(_account_policy_url(policy["id"])))
                full["reusable"] = True
                return full
            return policy
    raise CloudflareError(
        "Ingen allow-policy hittades på Access-applikationen — skapa en i "
        "Zero Trust-dashboarden först."
    )


async def _put_policy(policy: dict, include: list[dict]) -> list[str]:
    payload = {
        "name": policy["name"],
        "decision": policy["decision"],
        "include": include,
        "exclude": policy.get("exclude") or [],
        "require": policy.get("require") or [],
    }
    url = (
        _account_policy_url(policy["id"])
        if _is_reusable(policy)
        else _app_policy_url(policy["id"])
    )
    async with _client() as client:
        resp = await client.put(url, json=payload)
        if resp.status_code >= 400 and not _is_reusable(policy):
            # Äldre route funkade inte — policyn kan ändå vara återanvändbar
            logger.warning(
                "App-nivå-PUT misslyckades (%s) — provar kontonivå.",
                resp.status_code,
            )
            resp = await client.put(_account_policy_url(policy["id"]), json=payload)
        updated = _unwrap(resp)
    return _emails_from_include(updated.get("include") or [])


def _emails_from_include(include: list[dict]) -> list[str]:
    return sorted(
        entry["email"]["email"].lower()
        for entry in include
        if isinstance(entry, dict) and "email" in entry
    )


async def list_allowed_emails() -> list[str]:
    policy = await _get_policy()
    return _emails_from_include(policy.get("include") or [])


async def add_email(email: str) -> list[str]:
    email = email.lower().strip()
    policy = await _get_policy()
    include = list(policy.get("include") or [])
    if email in _emails_from_include(include):
        return _emails_from_include(include)
    include.append({"email": {"email": email}})
    return await _put_policy(policy, include)


async def remove_email(email: str) -> list[str]:
    email = email.lower().strip()
    policy = await _get_policy()
    include = [
        entry
        for entry in (policy.get("include") or [])
        if not (
            isinstance(entry, dict)
            and entry.get("email", {}).get("email", "").lower() == email
        )
    ]
    return await _put_policy(policy, include)
