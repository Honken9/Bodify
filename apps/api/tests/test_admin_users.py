import pytest
from sqlalchemy import func, select

from app.auth import ACCESS_JWT_HEADER
from app.models import User, WorkoutSession


def auth(make_token, email="daniel@example.com"):
    return {ACCESS_JWT_HEADER: make_token(email=email)}


@pytest.fixture
async def admin_user(db_session, known_user):
    known_user.is_admin = True
    await db_session.commit()
    return known_user


async def test_user_crud_requires_admin(client, make_token, known_user):
    assert (
        await client.post(
            "/api/admin/users",
            headers=auth(make_token),
            json={"email": "ny@example.com"},
        )
    ).status_code == 403


async def test_create_user_and_login(client, make_token, admin_user):
    resp = await client.post(
        "/api/admin/users",
        headers=auth(make_token),
        json={"email": "Kompis@Example.com", "display_name": "Kompis"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["email"] == "kompis@example.com"
    assert body["whitelisted"] is False  # CF-API:t inte konfigurerat i test

    # Duplikat avvisas
    dup = await client.post(
        "/api/admin/users",
        headers=auth(make_token),
        json={"email": "kompis@example.com"},
    )
    assert dup.status_code == 409

    # Den nya användaren kan logga in direkt
    me = await client.get(
        "/api/me", headers=auth(make_token, "kompis@example.com")
    )
    assert me.status_code == 200
    assert me.json()["display_name"] == "Kompis"


async def test_delete_user_cascades_data(
    client, make_token, admin_user, other_user, db_session
):
    # Anna loggar ett pass
    anna = auth(make_token, "anna@example.com")
    session = (
        await client.post("/api/sessions/start", headers=anna, json={})
    ).json()
    assert session["id"]

    resp = await client.delete(
        f"/api/admin/users/{other_user.id}", headers=auth(make_token)
    )
    assert resp.status_code == 200

    assert await db_session.scalar(
        select(func.count(User.id)).where(User.id == other_user.id)
    ) == 0
    # Kaskaden tog hennes pass
    assert await db_session.scalar(
        select(func.count(WorkoutSession.id)).where(
            WorkoutSession.user_id == other_user.id
        )
    ) == 0
    # Och hon kan inte längre logga in
    assert (await client.get("/api/me", headers=anna)).status_code == 403


async def test_cannot_delete_self(client, make_token, admin_user):
    resp = await client.delete(
        f"/api/admin/users/{admin_user.id}", headers=auth(make_token)
    )
    assert resp.status_code == 400


def test_cloudflare_policy_routing(monkeypatch):
    """Återanvändbara policies ska uppdateras via kontonivå-API:t."""
    from app.config import get_settings
    from app.integrations import cloudflare

    s = get_settings()
    monkeypatch.setattr(s, "cf_account_id", "acc-1")
    monkeypatch.setattr(s, "cf_access_app_id", "app-1")

    assert cloudflare._is_reusable({"reusable": True})
    assert not cloudflare._is_reusable({})
    assert (
        cloudflare._account_policy_url("pol-1")
        == "/accounts/acc-1/access/policies/pol-1"
    )
    assert (
        cloudflare._app_policy_url("pol-1")
        == "/accounts/acc-1/access/apps/app-1/policies/pol-1"
    )
