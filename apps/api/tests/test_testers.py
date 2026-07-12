import pytest

from app.auth import ACCESS_JWT_HEADER
from app.integrations import cloudflare


def auth(make_token, email="daniel@example.com"):
    return {ACCESS_JWT_HEADER: make_token(email=email)}


@pytest.fixture
async def admin_user(db_session, known_user):
    known_user.is_admin = True
    await db_session.commit()
    return known_user


@pytest.fixture
def fake_whitelist(monkeypatch):
    """Simulerar Cloudflare Access-policyn i minnet."""
    emails = {"daniel@example.com"}

    monkeypatch.setattr(cloudflare, "is_configured", lambda: True)

    async def fake_list():
        return sorted(emails)

    async def fake_add(email):
        emails.add(email.lower())
        return sorted(emails)

    async def fake_remove(email):
        emails.discard(email.lower())
        return sorted(emails)

    monkeypatch.setattr(cloudflare, "list_allowed_emails", fake_list)
    monkeypatch.setattr(cloudflare, "add_email", fake_add)
    monkeypatch.setattr(cloudflare, "remove_email", fake_remove)
    return emails


async def test_testers_requires_admin(client, make_token, known_user):
    resp = await client.get("/api/admin/testers", headers=auth(make_token))
    assert resp.status_code == 403


async def test_testers_unconfigured(client, make_token, admin_user):
    resp = await client.get("/api/admin/testers", headers=auth(make_token))
    assert resp.status_code == 200
    assert resp.json() == {"configured": False, "testers": []}

    invite = await client.post(
        "/api/admin/testers",
        headers=auth(make_token),
        json={"email": "test@example.com"},
    )
    assert invite.status_code == 503


async def test_invite_and_remove_tester(
    client, make_token, admin_user, other_user, fake_whitelist
):
    headers = auth(make_token)

    invite = await client.post(
        "/api/admin/testers",
        headers=headers,
        json={"email": "Testare@Example.com"},
    )
    assert invite.status_code == 201
    assert "testare@example.com" in invite.json()["emails"]

    listed = (await client.get("/api/admin/testers", headers=headers)).json()
    assert listed["configured"] is True
    by_email = {t["email"]: t for t in listed["testers"]}
    # Daniel finns i users-tabellen → har loggat in; nya testaren inte ännu
    assert by_email["daniel@example.com"]["has_logged_in"] is True
    assert by_email["testare@example.com"]["has_logged_in"] is False

    removed = await client.delete(
        "/api/admin/testers/testare@example.com", headers=headers
    )
    assert removed.status_code == 200
    assert "testare@example.com" not in removed.json()["emails"]


async def test_cannot_remove_own_access(
    client, make_token, admin_user, fake_whitelist
):
    resp = await client.delete(
        "/api/admin/testers/daniel@example.com", headers=auth(make_token)
    )
    assert resp.status_code == 400


async def test_invalid_email_rejected(client, make_token, admin_user, fake_whitelist):
    resp = await client.post(
        "/api/admin/testers",
        headers=auth(make_token),
        json={"email": "inte-en-adress"},
    )
    assert resp.status_code == 422
