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


async def test_steps_challenge_and_home_summary(
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
                "name": "Stegkriget",
                "metric": "steps_total",
                "starts_on": (today - timedelta(days=3)).isoformat(),
                "ends_on": (today + timedelta(days=3)).isoformat(),
            },
        )
    ).json()
    await client.post(
        f"/api/social/challenges/{challenge['id']}/join", headers=anna
    )

    # Daniel: 8000+6000 steg (två källor samma dag → högsta vinner)
    for value, days_ago in ((8000, 1), (6000, 0)):
        await client.post(
            "/api/metrics",
            headers=daniel,
            json={
                "metric": "steps",
                "value": value,
                "measured_at": (
                    datetime.now(timezone.utc) - timedelta(days=days_ago)
                ).isoformat(),
            },
        )
    await client.post(
        "/api/metrics",
        headers=anna,
        json={"metric": "steps", "value": 20000},
    )

    detail = (
        await client.get(
            f"/api/social/challenges/{challenge['id']}", headers=daniel
        )
    ).json()
    values = {r["name"]: r["value"] for r in detail["leaderboard"]}
    assert values["Anna"] == 20000
    assert values["Daniel"] == 14000  # 8000 + 6000, olika dagar

    # Hemskärmskortet: Daniel 2:a, gapet till Anna = 6000
    summary = (
        await client.get(
            "/api/social/challenges/active-summary", headers=daniel
        )
    ).json()
    assert summary[0]["my_rank"] == 2
    assert summary[0]["gap_ahead"]["name"] == "Anna"
    assert summary[0]["gap_ahead"]["diff"] == 6000


async def test_open_challenge_joinable_without_friendship(
    client, make_token, known_user, other_user
):
    # Anna är INTE vän med Daniel — men utmaningen är öppen
    daniel = auth(make_token)
    anna = auth(make_token, "anna@example.com")
    today = date.today()
    challenge = (
        await client.post(
            "/api/social/challenges",
            headers=daniel,
            json={
                "name": "Öppna stegkriget",
                "metric": "steps_total",
                "starts_on": today.isoformat(),
                "ends_on": (today + timedelta(days=6)).isoformat(),
                "is_open": True,
            },
        )
    ).json()
    assert challenge["is_open"] is True

    # Syns i Annas lista + går att gå med
    names = [
        c["name"]
        for c in (
            await client.get("/api/social/challenges", headers=anna)
        ).json()
    ]
    assert "Öppna stegkriget" in names
    join = await client.post(
        f"/api/social/challenges/{challenge['id']}/join", headers=anna
    )
    assert join.status_code == 200


async def test_habit_challenge_counts_weeks(
    client, make_token, known_user, other_user, friends
):
    daniel = auth(make_token)
    today = date.today()
    challenge = (
        await client.post(
            "/api/social/challenges",
            headers=daniel,
            json={
                "name": "Träningsvanan",
                "metric": "workout_count",
                "kind": "habit",
                "target_per_week": 2,
                "starts_on": (today - timedelta(days=6)).isoformat(),
                "ends_on": (today + timedelta(days=7)).isoformat(),
            },
        )
    ).json()
    assert challenge["metric_label"] == "Vana: 2 pass/vecka"

    # Två pass första veckan → 1 klarad vecka
    for _ in range(2):
        s = (
            await client.post("/api/sessions/start", headers=daniel, json={})
        ).json()
        await client.post(
            f"/api/sessions/{s['id']}/finish", headers=daniel, json={}
        )

    detail = (
        await client.get(
            f"/api/social/challenges/{challenge['id']}", headers=daniel
        )
    ).json()
    assert detail["habit"]["completed"] == 1
    assert detail["habit"]["total"] == 2
    assert detail["leaderboard"][0]["value"] == 1.0


async def test_trophies_and_rematch(
    client, make_token, known_user, other_user, friends, db_session
):
    from app.models import Challenge

    daniel = auth(make_token)
    anna = auth(make_token, "anna@example.com")
    today = date.today()

    challenge = (
        await client.post(
            "/api/social/challenges",
            headers=daniel,
            json={
                "name": "Avgjorda kriget",
                "metric": "workout_count",
                "starts_on": (today - timedelta(days=14)).isoformat(),
                "ends_on": (today - timedelta(days=8)).isoformat(),
            },
        )
    ).json()
    await client.post(
        f"/api/social/challenges/{challenge['id']}/join", headers=anna
    )

    trophies = (
        await client.get("/api/social/trophies", headers=daniel)
    ).json()
    assert trophies[0]["name"] == "Avgjorda kriget"
    assert trophies[0]["rank"] in (1, 2)

    # Revansch: ny utmaning, gamla deltagare bjuds in
    rematch = await client.post(
        f"/api/social/challenges/{challenge['id']}/rematch", headers=daniel
    )
    assert rematch.status_code == 201
    assert "revansch" in rematch.json()["name"]
    anna_list = (
        await client.get("/api/social/challenges", headers=anna)
    ).json()
    invited = [c for c in anna_list if c.get("invited")]
    assert any("revansch" in c["name"] for c in invited)


async def test_challenge_feed_and_cheer(
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
                "name": "Flödestestet",
                "metric": "workout_count",
                "starts_on": (today - timedelta(days=1)).isoformat(),
                "ends_on": (today + timedelta(days=6)).isoformat(),
            },
        )
    ).json()
    await client.post(
        f"/api/social/challenges/{challenge['id']}/join", headers=anna
    )

    s = (await client.post("/api/sessions/start", headers=anna, json={})).json()
    await client.post(f"/api/sessions/{s['id']}/finish", headers=anna, json={})

    feed = (
        await client.get(
            f"/api/social/challenges/{challenge['id']}/feed", headers=daniel
        )
    ).json()
    assert feed[0]["user_name"] == "Anna"
    assert feed[0]["cheers"] == 0

    item = feed[0]
    resp = await client.post(
        f"/api/social/challenges/{challenge['id']}/cheer",
        headers=daniel,
        json={
            "item_kind": item["kind"],
            "item_id": item["id"],
            "owner_id": item["user_id"],
        },
    )
    assert resp.json()["cheered"] is True

    feed = (
        await client.get(
            f"/api/social/challenges/{challenge['id']}/feed", headers=anna
        )
    ).json()
    assert feed[0]["cheers"] == 1


async def test_weekly_challenges_created_by_job(
    client, make_token, db_session, known_user, monkeypatch
):
    from app.services import challenges as challenge_service

    known_user.is_admin = True
    await db_session.commit()

    created = await challenge_service.ensure_weekly_challenges(db_session)
    assert created == 2
    # Körs igen → inga dubbletter
    assert await challenge_service.ensure_weekly_challenges(db_session) == 0

    names = [
        c["name"]
        for c in (
            await client.get(
                "/api/social/challenges", headers=auth(make_token)
            )
        ).json()
    ]
    assert any("stegkrig" in n.lower() for n in names)
    assert any("Sömnligan" in n for n in names)


async def test_admin_overview(client, make_token, db_session, known_user):
    known_user.is_admin = True
    await db_session.commit()

    overview = (
        await client.get("/api/admin/overview", headers=auth(make_token))
    ).json()
    assert overview["users"] == 1
    assert "connections" in overview
