import pytest

from app.auth import ACCESS_JWT_HEADER


def auth(make_token, email="daniel@example.com"):
    return {ACCESS_JWT_HEADER: make_token(email=email)}


@pytest.fixture
async def two_exercises(client, make_token, known_user):
    ids = []
    for name, muscles in [("Bänkpress", ["bröst"]), ("Knäböj", ["ben"])]:
        resp = await client.post(
            "/api/exercises",
            headers=auth(make_token),
            json={"name": name, "muscle_groups": muscles, "equipment": ["skivstång"]},
        )
        assert resp.status_code == 201
        ids.append(resp.json()["id"])
    return ids


@pytest.fixture
async def activated_program(client, make_token, known_user, two_exercises):
    """Tvådagarsprogram (rullande A/B) skapat och aktiverat för Daniel."""
    bench, squat = two_exercises
    resp = await client.post(
        "/api/programs",
        headers=auth(make_token),
        json={
            "name": "A/B-split",
            "level": "beginner",
            "days_per_week": 4,
            "days": [
                {"name": "Pass A", "exercises": [{"exercise_id": bench}]},
                {"name": "Pass B", "exercises": [{"exercise_id": squat}]},
            ],
        },
    )
    assert resp.status_code == 201
    program = resp.json()

    resp = await client.post(
        f"/api/programs/{program['id']}/activate", headers=auth(make_token)
    )
    assert resp.status_code == 200
    return program


async def test_custom_exercise_is_private(
    client, make_token, known_user, other_user, two_exercises
):
    mine = await client.get("/api/exercises", headers=auth(make_token))
    assert {e["name"] for e in mine.json()} == {"Bänkpress", "Knäböj"}

    theirs = await client.get(
        "/api/exercises", headers=auth(make_token, "anna@example.com")
    )
    assert theirs.json() == []


async def test_muscle_filter(client, make_token, known_user, two_exercises):
    resp = await client.get(
        "/api/exercises?muscle=ben", headers=auth(make_token)
    )
    assert [e["name"] for e in resp.json()] == ["Knäböj"]


async def test_activate_and_active_endpoint(
    client, make_token, known_user, activated_program
):
    resp = await client.get("/api/user-programs/active", headers=auth(make_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["program"]["name"] == "A/B-split"
    assert body["next_day_position"] == 0
    assert body["is_active"] is True


async def test_rolling_split_advances_and_wraps(
    client, make_token, known_user, activated_program
):
    days = activated_program["days"]

    for expected_next in (1, 0):  # Pass A → nästa = B; Pass B → tillbaka till A
        active = (await client.get(
            "/api/user-programs/active", headers=auth(make_token)
        )).json()
        day = days[active["next_day_position"]]

        start = await client.post(
            "/api/sessions/start",
            headers=auth(make_token),
            json={"program_day_id": day["id"]},
        )
        assert start.status_code == 201
        session_id = start.json()["id"]

        finish = await client.post(
            f"/api/sessions/{session_id}/finish",
            headers=auth(make_token),
            json={},
        )
        assert finish.status_code == 200

        active = (await client.get(
            "/api/user-programs/active", headers=auth(make_token)
        )).json()
        assert active["next_day_position"] == expected_next


async def test_previous_sets_shown_in_next_session(
    client, make_token, known_user, activated_program, two_exercises
):
    bench = two_exercises[0]
    day_a = activated_program["days"][0]

    # Pass 1: logga två set bänkpress och avsluta
    start = await client.post(
        "/api/sessions/start",
        headers=auth(make_token),
        json={"program_day_id": day_a["id"]},
    )
    session_id = start.json()["id"]
    assert start.json()["plan"][0]["previous"] is None  # inget tidigare pass

    for weight, reps in [(80, 10), (85, 8)]:
        resp = await client.post(
            f"/api/sessions/{session_id}/sets",
            headers=auth(make_token),
            json={"exercise_id": bench, "weight_kg": weight, "reps": reps},
        )
        assert resp.status_code == 201
    await client.post(
        f"/api/sessions/{session_id}/finish", headers=auth(make_token), json={}
    )

    # Pass 2 (samma dag): föregående vikt/reps ska visas inline
    start2 = await client.post(
        "/api/sessions/start",
        headers=auth(make_token),
        json={"program_day_id": day_a["id"]},
    )
    plan = start2.json()["plan"][0]
    assert plan["exercise"]["id"] == bench
    previous = plan["previous"]
    assert previous is not None
    assert [(s["weight_kg"], s["reps"]) for s in previous["sets"]] == [
        (80.0, 10),
        (85.0, 8),
    ]


async def test_set_numbering_per_exercise(
    client, make_token, known_user, two_exercises
):
    bench, squat = two_exercises
    start = await client.post(
        "/api/sessions/start", headers=auth(make_token), json={}
    )
    session_id = start.json()["id"]

    numbers = []
    for ex in (bench, bench, squat):
        resp = await client.post(
            f"/api/sessions/{session_id}/sets",
            headers=auth(make_token),
            json={"exercise_id": ex, "weight_kg": 60, "reps": 10},
        )
        numbers.append(resp.json()["set_number"])
    assert numbers == [1, 2, 1]


async def test_cannot_add_set_to_finished_session(
    client, make_token, known_user, two_exercises
):
    start = await client.post(
        "/api/sessions/start", headers=auth(make_token), json={}
    )
    session_id = start.json()["id"]
    await client.post(
        f"/api/sessions/{session_id}/finish", headers=auth(make_token), json={}
    )
    resp = await client.post(
        f"/api/sessions/{session_id}/sets",
        headers=auth(make_token),
        json={"exercise_id": two_exercises[0], "weight_kg": 60, "reps": 10},
    )
    assert resp.status_code == 409


async def test_session_history_with_volume(
    client, make_token, known_user, two_exercises
):
    bench = two_exercises[0]
    start = await client.post(
        "/api/sessions/start", headers=auth(make_token), json={}
    )
    session_id = start.json()["id"]
    await client.post(
        f"/api/sessions/{session_id}/sets",
        headers=auth(make_token),
        json={"exercise_id": bench, "weight_kg": 100, "reps": 5},
    )
    await client.post(
        f"/api/sessions/{session_id}/finish",
        headers=auth(make_token),
        json={"notes": "Bra pass!"},
    )

    resp = await client.get("/api/sessions", headers=auth(make_token))
    assert resp.status_code == 200
    [summary] = resp.json()
    assert summary["set_count"] == 1
    assert summary["total_volume_kg"] == 500.0
    assert summary["notes"] == "Bra pass!"


async def test_user_isolation(
    client, make_token, known_user, other_user, activated_program, two_exercises
):
    # Daniel startar ett pass
    start = await client.post(
        "/api/sessions/start", headers=auth(make_token), json={}
    )
    session_id = start.json()["id"]

    anna = auth(make_token, "anna@example.com")

    # Anna ser inte Daniels pass, program eller session
    assert (await client.get("/api/sessions", headers=anna)).json() == []
    assert (
        await client.get(f"/api/sessions/{session_id}", headers=anna)
    ).status_code == 404
    assert (
        await client.post(
            f"/api/sessions/{session_id}/sets",
            headers=anna,
            json={"exercise_id": two_exercises[0], "weight_kg": 50, "reps": 10},
        )
    ).status_code == 404
    assert (
        await client.post(
            f"/api/programs/{activated_program['id']}/activate", headers=anna
        )
    ).status_code == 404
    assert (
        await client.get("/api/user-programs/active", headers=anna)
    ).json() is None
