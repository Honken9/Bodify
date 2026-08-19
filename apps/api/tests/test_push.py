from app.auth import ACCESS_JWT_HEADER


async def test_apns_token_register_and_remove(client, make_token, known_user):
    headers = {ACCESS_JWT_HEADER: make_token(email="daniel@example.com")}
    token = "ab" * 32  # 64 hex-tecken

    r = await client.post(
        "/api/push/apns-token", headers=headers, json={"token": token.upper()}
    )
    assert r.status_code == 201

    # Idempotent upsert
    r = await client.post(
        "/api/push/apns-token", headers=headers, json={"token": token}
    )
    assert r.status_code == 201

    # Ogiltig token avvisas
    r = await client.post(
        "/api/push/apns-token", headers=headers, json={"token": "xyz!"}
    )
    assert r.status_code == 422

    r = await client.delete(f"/api/push/apns-token/{token}", headers=headers)
    assert r.status_code == 204


async def test_apns_send_noop_without_config(db_session, known_user):
    from app import apns

    sent = await apns.send_to_user(
        db_session, known_user.id, "Test", "Hej", url="/"
    )
    assert sent == 0
