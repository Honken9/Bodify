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
    body = resp.json()
    if not body.get("success"):
        raise CloudflareError(f"Cloudflare-fel: {body.get('errors')}")
    return body["result"]


async def _get_policy() -> dict:
    """Hämta policyn som bär e-postvitlistan."""
    _require_config()
    s = get_settings()
    base = f"/accounts/{s.cf_account_id}/access/apps/{s.cf_access_app_id}/policies"
    async with _client() as client:
        if s.cf_access_policy_id:
            return _unwrap(await client.get(f"{base}/{s.cf_access_policy_id}"))
        policies = _unwrap(await client.get(base))
    for policy in policies:
        if policy.get("decision") == "allow":
            return policy
    raise CloudflareError(
        "Ingen allow-policy hittades på Access-applikationen — skapa en i "
        "Zero Trust-dashboarden först."
    )


async def _put_policy(policy: dict, include: list[dict]) -> list[str]:
    s = get_settings()
    payload = {
        "name": policy["name"],
        "decision": policy["decision"],
        "include": include,
        "exclude": policy.get("exclude") or [],
        "require": policy.get("require") or [],
    }
    url = (
        f"/accounts/{s.cf_account_id}/access/apps/"
        f"{s.cf_access_app_id}/policies/{policy['id']}"
    )
    async with _client() as client:
        updated = _unwrap(await client.put(url, json=payload))
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
