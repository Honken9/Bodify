from datetime import date, timedelta

import pytest

from app.auth import ACCESS_JWT_HEADER


def auth(make_token, email="daniel@example.com"):
    return {ACCESS_JWT_HEADER: make_token(email=email)}


@pytest.fixture
async def challenge(client, make_token, known_user):
    """Daniel skapar en utmaning (Anna är INTE vän med Daniel)."""
    today = date.today()
    return (
        await client.post(
            "/api/social/challenges",
            headers=auth(make_token),
            json={
                "name": "Gruppracet",
                "metric": "workout_count",
                "starts_on": today.isoformat(),
                "ends_on": (today + timedelta(days=14)).isoformat(),
            },
        )
    ).json()


async def test_invite_lets_non_friend_join(
    client, make_token, known_user, other_user, challenge
):
    daniel = auth(make_token)
    anna = auth(make_token, "anna@example.com")

    # Utan inbjudan: Anna ser inget och får inte gå med
    assert (await client.get("/api/social/challenges", headers=anna)).json() == []
    assert (
        await client.post(
            f"/api/social/challenges/{challenge['id']}/join", headers=anna
        )
    ).status_code == 403

    # Daniel bjuder in Anna
    resp = await client.post(
        f"/api/social/challenges/{challenge['id']}/invite",
        headers=daniel,
        json={"email": "anna@example.com"},
    )
    assert resp.status_code == 201

    # Nu ser Anna utmaningen, flaggad som inbjudan
    [seen] = (await client.get("/api/social/challenges", headers=anna)).json()
    assert seen["invited"] is True
    assert seen["is_participant"] is False

    # ...och kan gå med trots att hon inte är vän med Daniel
    join = await client.post(
        f"/api/social/challenges/{challenge['id']}/join", headers=anna
    )
    assert join.status_code == 200

    detail = (
        await client.get(
            f"/api/social/challenges/{challenge['id']}", headers=anna
        )
    ).json()
    assert detail["is_participant"] is True
    assert len(detail["leaderboard"]) == 2


async def test_only_participants_can_invite(
    client, make_token, known_user, other_user, challenge
):
    anna = auth(make_token, "anna@example.com")
    resp = await client.post(
        f"/api/social/challenges/{challenge['id']}/invite",
        headers=anna,
        json={"email": "daniel@example.com"},
    )
    assert resp.status_code in (403, 404)  # ej deltagare (404 om osynlig)


async def test_invite_unknown_email(client, make_token, known_user, challenge):
    resp = await client.post(
        f"/api/social/challenges/{challenge['id']}/invite",
        headers=auth(make_token),
        json={"email": "finns-inte@example.com"},
    )
    assert resp.status_code == 404


async def test_invite_is_idempotent_and_blocks_participants(
    client, make_token, known_user, other_user, challenge
):
    daniel = auth(make_token)
    await client.post(
        f"/api/social/challenges/{challenge['id']}/invite",
        headers=daniel,
        json={"email": "anna@example.com"},
    )
    again = await client.post(
        f"/api/social/challenges/{challenge['id']}/invite",
        headers=daniel,
        json={"email": "anna@example.com"},
    )
    assert again.json().get("already_invited") is True

    # Redan deltagare → 409
    dup = await client.post(
        f"/api/social/challenges/{challenge['id']}/invite",
        headers=daniel,
        json={"email": "daniel@example.com"},
    )
    assert dup.status_code == 409
