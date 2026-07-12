from datetime import date, datetime, timedelta, timezone

import pytest

from app.auth import ACCESS_JWT_HEADER


def auth(make_token, email="daniel@example.com"):
    return {ACCESS_JWT_HEADER: make_token(email=email)}


@pytest.fixture
async def friends(client, make_token, known_user, other_user):
    """Daniel och Anna är vänner."""
    await client.post(
        "/api/social/friends",
        headers=auth(make_token),
        json={"email": "anna@example.com"},
    )
    incoming = (
        await client.get(
            "/api/social/friends", headers=auth(make_token, "anna@example.com")
        )
    ).json()["incoming"]
    await client.post(
        f"/api/social/friends/{incoming[0]['friendship_id']}/accept",
        headers=auth(make_token, "anna@example.com"),
    )


async def test_friend_request_flow(client, make_token, known_user, other_user):
    resp = await client.post(
        "/api/social/friends",
        headers=auth(make_token),
        json={"email": "anna@example.com"},
    )
    assert resp.status_code == 201

    anna = auth(make_token, "anna@example.com")
    incoming = (await client.get("/api/social/friends", headers=anna)).json()[
        "incoming"
    ]
    assert incoming[0]["email"] == "daniel@example.com"

    await client.post(
        f"/api/social/friends/{incoming[0]['friendship_id']}/accept",
        headers=anna,
    )
    mine = (
        await client.get("/api/social/friends", headers=auth(make_token))
    ).json()
    assert mine["friends"][0]["email"] == "anna@example.com"

    # Dubblettförfrågan avvisas
    dup = await client.post(
        "/api/social/friends", headers=anna, json={"email": "daniel@example.com"}
    )
    assert dup.status_code == 409


async def test_friend_request_unknown_email(client, make_token, known_user):
    resp = await client.post(
        "/api/social/friends",
        headers=auth(make_token),
        json={"email": "okand@example.com"},
    )
    assert resp.status_code == 404


async def test_challenge_workout_count_leaderboard(
    client, make_token, known_user, other_user, friends
):
    daniel = auth(make_token)
    anna = auth(make_token, "anna@example.com")

    today = date.today()
    challenge = (
        await client.post(
            "/api/social/challenges",
            headers=daniel,
            json={
                "name": "Juli-utmaningen",
                "metric": "workout_count",
                "starts_on": (today - timedelta(days=7)).isoformat(),
                "ends_on": (today + timedelta(days=7)).isoformat(),
            },
        )
    ).json()
    assert challenge["is_participant"] is True

    join = await client.post(
        f"/api/social/challenges/{challenge['id']}/join", headers=anna
    )
    assert join.status_code == 200

    # Anna kör två pass, Daniel ett
    async def do_workout(headers):
        s = (
            await client.post("/api/sessions/start", headers=headers, json={})
        ).json()
        await client.post(
            f"/api/sessions/{s['id']}/finish", headers=headers, json={}
        )

    await do_workout(anna)
    await do_workout(anna)
    await do_workout(daniel)

    detail = (
        await client.get(
            f"/api/social/challenges/{challenge['id']}", headers=daniel
        )
    ).json()
    board = detail["leaderboard"]
    assert board[0]["name"] == "Anna"
    assert board[0]["value"] == 2.0
    assert board[0]["rank"] == 1
    assert board[1]["name"] == "Daniel"
    assert board[1]["value"] == 1.0


async def test_weight_loss_challenge_locks_baseline(
    client, make_token, known_user, other_user, friends
):
    daniel = auth(make_token)
    await client.post(
        "/api/metrics", headers=daniel, json={"metric": "weight", "value": 84.0}
    )

    today = date.today()
    challenge = (
        await client.post(
            "/api/social/challenges",
            headers=daniel,
            json={
                "name": "Sommardeff",
                "metric": "weight_loss_kg",
                "starts_on": today.isoformat(),
                "ends_on": (today + timedelta(days=30)).isoformat(),
            },
        )
    ).json()

    # Ny mätning under perioden: 82.5 → nedgång 1.5 kg
    await client.post(
        "/api/metrics",
        headers=daniel,
        json={
            "metric": "weight",
            "value": 82.5,
            "measured_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    detail = (
        await client.get(
            f"/api/social/challenges/{challenge['id']}", headers=daniel
        )
    ).json()
    row = detail["leaderboard"][0]
    assert row["baseline"] == {"weight": 84.0}
    assert row["value"] == 1.5


async def test_weight_challenge_requires_baseline(
    client, make_token, known_user, other_user, friends
):
    anna = auth(make_token, "anna@example.com")
    daniel = auth(make_token)
    await client.post(
        "/api/metrics", headers=daniel, json={"metric": "weight", "value": 84.0}
    )
    today = date.today()
    challenge = (
        await client.post(
            "/api/social/challenges",
            headers=daniel,
            json={
                "name": "Deff",
                "metric": "weight_loss_kg",
                "starts_on": today.isoformat(),
                "ends_on": (today + timedelta(days=10)).isoformat(),
            },
        )
    ).json()
    # Anna saknar viktmätning → tydligt fel
    resp = await client.post(
        f"/api/social/challenges/{challenge['id']}/join", headers=anna
    )
    assert resp.status_code == 400


async def test_non_friend_cannot_join_or_see(
    client, make_token, known_user, other_user
):
    daniel = auth(make_token)
    anna = auth(make_token, "anna@example.com")
    today = date.today()
    challenge = (
        await client.post(
            "/api/social/challenges",
            headers=daniel,
            json={
                "name": "Privat",
                "metric": "workout_count",
                "starts_on": today.isoformat(),
                "ends_on": (today + timedelta(days=7)).isoformat(),
            },
        )
    ).json()

    assert (
        await client.post(
            f"/api/social/challenges/{challenge['id']}/join", headers=anna
        )
    ).status_code == 403
    assert (
        await client.get(
            f"/api/social/challenges/{challenge['id']}", headers=anna
        )
    ).status_code == 404
    assert (await client.get("/api/social/challenges", headers=anna)).json() == []


async def test_snapshot_job(client, make_token, known_user, other_user, friends, db_session):
    daniel = auth(make_token)
    today = date.today()
    await client.post(
        "/api/social/challenges",
        headers=daniel,
        json={
            "name": "Pågående",
            "metric": "workout_count",
            "starts_on": (today - timedelta(days=1)).isoformat(),
            "ends_on": (today + timedelta(days=5)).isoformat(),
        },
    )

    from app.services.challenges import run_daily_snapshots

    result = await run_daily_snapshots(db_session)
    assert result["snapshots"] == 1  # en deltagare (skaparen)

    # Idempotent för samma dag
    result2 = await run_daily_snapshots(db_session)
    assert result2["snapshots"] == 1


async def test_admin_overview(client, make_token, db_session, known_user):
    known_user.is_admin = True
    await db_session.commit()

    overview = (
        await client.get("/api/admin/overview", headers=auth(make_token))
    ).json()
    assert overview["users"] == 1
    assert "connections" in overview
