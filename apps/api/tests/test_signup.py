from app.auth import ACCESS_JWT_HEADER


async def test_signup_with_club_code(client, make_token, known_user):
    daniel = {ACCESS_JWT_HEADER: make_token(email="daniel@example.com")}

    # Daniel skapar en liga → koden blir inbjudningsbiljetten
    r = await client.post(
        "/api/social/clubs", headers=daniel, json={"name": "Onboardingligan"}
    )
    code = r.json()["invite_code"]

    # Ny användare registrerar sig med ligakoden — helt utan inloggning
    r = await client.post(
        "/api/webhooks/signup",
        json={"email": "Nya@Example.com", "display_name": "Nya", "code": code.lower()},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["created"] is True
    assert data["club"] == "Onboardingligan"

    # Registreringen är idempotent — samma mejl igen skapar inget nytt
    r = await client.post(
        "/api/webhooks/signup",
        json={"email": "nya@example.com", "code": code},
    )
    assert r.status_code == 201
    assert r.json()["created"] is False

    # Ligan har nu två medlemmar
    r = await client.get("/api/social/clubs", headers=daniel)
    assert r.json()[0]["member_count"] == 2


async def test_signup_rejects_bad_code_and_email(client, known_user):
    r = await client.post(
        "/api/webhooks/signup",
        json={"email": "x@example.com", "code": "FELKOD99"},
    )
    assert r.status_code == 404

    r = await client.post(
        "/api/webhooks/signup",
        json={"email": "inte-en-mejl", "code": "FELKOD99"},
    )
    assert r.status_code == 400
