from app.auth import ACCESS_JWT_HEADER


async def test_healthz_requires_no_auth(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_me_without_token_is_401(client):
    resp = await client.get("/api/me")
    assert resp.status_code == 401


async def test_me_with_valid_token_and_known_user(client, make_token, known_user):
    resp = await client.get(
        "/api/me", headers={ACCESS_JWT_HEADER: make_token()}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "daniel@example.com"
    assert body["display_name"] == "Daniel"
    assert body["is_admin"] is False


async def test_me_with_wrong_audience_is_401(client, make_token, known_user):
    resp = await client.get(
        "/api/me", headers={ACCESS_JWT_HEADER: make_token(aud="fel-aud")}
    )
    assert resp.status_code == 401


async def test_me_with_wrong_issuer_is_401(client, make_token, known_user):
    resp = await client.get(
        "/api/me",
        headers={ACCESS_JWT_HEADER: make_token(iss="https://ond.example.com")},
    )
    assert resp.status_code == 401


async def test_token_without_email_is_401(client, make_token):
    resp = await client.get(
        "/api/me", headers={ACCESS_JWT_HEADER: make_token(email=None)}
    )
    assert resp.status_code == 401


async def test_unknown_user_is_403(client, make_token):
    resp = await client.get(
        "/api/me", headers={ACCESS_JWT_HEADER: make_token(email="okand@example.com")}
    )
    assert resp.status_code == 403


async def test_email_lookup_is_case_insensitive(client, make_token, known_user):
    resp = await client.get(
        "/api/me", headers={ACCESS_JWT_HEADER: make_token(email="Daniel@Example.com")}
    )
    assert resp.status_code == 200


async def test_admin_route_requires_admin(client, make_token, known_user):
    resp = await client.get(
        "/api/admin/users", headers={ACCESS_JWT_HEADER: make_token()}
    )
    assert resp.status_code == 403


async def test_update_display_name(client, make_token, known_user):
    resp = await client.patch(
        "/api/me",
        headers={ACCESS_JWT_HEADER: make_token()},
        json={"display_name": "Danne"},
    )
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Danne"
