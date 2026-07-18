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


async def test_profile_update_and_merge(client, make_token, known_user):
    from app.auth import ACCESS_JWT_HEADER

    headers = {ACCESS_JWT_HEADER: make_token(email="daniel@example.com")}
    resp = await client.patch(
        "/api/me",
        headers=headers,
        json={
            "display_name": "Danne",
            "profile": {
                "city": "Stockholm",
                "fav_workout": "Gym & löpning",
                "fav_exercise": "Marklyft",
                "goal": "Mila under 50 min",
            },
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["display_name"] == "Danne"
    assert body["profile"]["city"] == "Stockholm"
    assert body["avatar_url"] is None

    # Delvis uppdatering skriver inte över övriga fält; tomt värde rensar
    resp = await client.patch(
        "/api/me",
        headers=headers,
        json={"profile": {"city": "Göteborg", "goal": ""}},
    )
    profile = resp.json()["profile"]
    assert profile["city"] == "Göteborg"
    assert profile["fav_exercise"] == "Marklyft"
    assert "goal" not in profile


async def test_avatar_upload_and_fetch(
    client, make_token, known_user, tmp_path, monkeypatch
):
    import io

    from app.auth import ACCESS_JWT_HEADER
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "data_dir", str(tmp_path))
    headers = {ACCESS_JWT_HEADER: make_token(email="daniel@example.com")}

    # Skräpinnehåll avvisas oavsett påstådd filtyp
    bad = await client.post(
        "/api/me/avatar",
        headers=headers,
        files={"file": ("x.jpg", io.BytesIO(b"inte en bild"), "image/jpeg")},
    )
    assert bad.status_code == 400

    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    ok = await client.post(
        "/api/me/avatar",
        headers=headers,
        files={"file": ("avatar.png", io.BytesIO(png), "image/png")},
    )
    assert ok.status_code == 200
    assert ok.json()["avatar_url"].startswith("/api/me/avatar")

    fetched = await client.get("/api/me/avatar", headers=headers)
    assert fetched.status_code == 200
    assert fetched.headers["content-type"] == "image/png"

    # Ta bort → 404 vid hämtning
    assert (
        await client.delete("/api/me/avatar", headers=headers)
    ).status_code == 204
    assert (await client.get("/api/me/avatar", headers=headers)).status_code == 404
