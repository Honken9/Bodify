import io
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.ai import ollama
from app.auth import ACCESS_JWT_HEADER
from app.models import BodyMetric, SleepSession


def auth(make_token, email="daniel@example.com"):
    return {ACCESS_JWT_HEADER: make_token(email=email)}


@pytest.fixture
async def exercise_library(client, make_token, known_user):
    ids = {}
    for name, muscles, equipment in [
        ("Knäböj", ["ben"], ["skivstång"]),
        ("Bänkpress", ["bröst"], ["skivstång"]),
        ("Hantelrodd", ["rygg"], ["hantlar"]),
        ("Armhävningar", ["bröst"], ["kroppsvikt"]),
    ]:
        resp = await client.post(
            "/api/exercises",
            headers=auth(make_token),
            json={"name": name, "muscle_groups": muscles, "equipment": equipment},
        )
        ids[name] = resp.json()["id"]
    return ids


async def test_generate_workout_validates_and_accepts(
    client, make_token, known_user, exercise_library, monkeypatch
):
    async def fake_chat(prompt, **kwargs):
        return json.dumps(
            {
                "name": "Snabbt helkroppspass",
                "exercises": [
                    {"name": "Knäböj", "sets": 3, "reps": "8-10", "rest_seconds": 120},
                    {"name": "bänkpress", "sets": 3, "reps": "8-12", "rest_seconds": 90},
                    {"name": "Påhittad övning", "sets": 3, "reps": "10", "rest_seconds": 60},
                ],
            }
        )

    monkeypatch.setattr(ollama, "chat", fake_chat)

    plan = (
        await client.post(
            "/api/ai/generate-workout",
            headers=auth(make_token),
            json={"minutes": 30, "equipment": ["skivstång"]},
        )
    ).json()
    # Hallucinerad övning filtreras bort, case-insensitive matchning funkar
    assert [e["name"] for e in plan["exercises"]] == ["Knäböj", "Bänkpress"]

    accepted = (
        await client.post(
            "/api/ai/generate-workout/accept",
            headers=auth(make_token),
            json={"plan": plan},
        )
    ).json()
    day_id = accepted["program_day_id"]

    # Passet går att starta som vanligt — med targets från planen
    session = (
        await client.post(
            "/api/sessions/start",
            headers=auth(make_token),
            json={"program_day_id": day_id},
        )
    ).json()
    assert session["day_name"] == "Snabbt helkroppspass"
    assert session["plan"][0]["target_sets"] == 3


async def test_generate_workout_unusable_response(
    client, make_token, known_user, exercise_library, monkeypatch
):
    async def fake_chat(prompt, **kwargs):
        return json.dumps(
            {
                "name": "Trams",
                "exercises": [
                    {"name": "Finns inte 1", "sets": 3, "reps": "10", "rest_seconds": 60},
                    {"name": "Finns inte 2", "sets": 3, "reps": "10", "rest_seconds": 60},
                ],
            }
        )

    monkeypatch.setattr(ollama, "chat", fake_chat)
    resp = await client.post(
        "/api/ai/generate-workout", headers=auth(make_token), json={}
    )
    assert resp.status_code == 502


async def test_generate_workout_ollama_down(
    client, make_token, known_user, exercise_library, monkeypatch
):
    async def fake_chat(prompt, **kwargs):
        raise ollama.AIUnavailable("nere")

    monkeypatch.setattr(ollama, "chat", fake_chat)
    resp = await client.post(
        "/api/ai/generate-workout", headers=auth(make_token), json={}
    )
    assert resp.status_code == 503


async def test_gym_vision_maps_equipment(
    client, make_token, known_user, exercise_library, monkeypatch
):
    async def fake_chat(prompt, **kwargs):
        assert kwargs.get("images_b64")  # bilden skickas med
        return json.dumps({"equipment": ["skivstång", "rymdskepp"]})

    monkeypatch.setattr(ollama, "chat", fake_chat)
    resp = await client.post(
        "/api/ai/gym-vision",
        headers=auth(make_token),
        files={"file": ("gym.jpg", io.BytesIO(b"fake-jpeg"), "image/jpeg")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["equipment"] == ["skivstång"]  # okänt ord filtreras
    names = [e["name"] for e in body["exercises"]]
    assert "Knäböj" in names and "Bänkpress" in names
    assert "Hantelrodd" not in names  # kräver hantlar


async def test_readiness_no_data(client, make_token, known_user):
    result = (
        await client.get("/api/ai/readiness", headers=auth(make_token))
    ).json()
    assert result["status"] == "unknown"


async def test_readiness_red_on_low_hrv_and_bad_sleep(
    client, make_token, known_user, db_session
):
    now = datetime.now(timezone.utc)
    # 28 dagar HRV kring 60 ms, senaste veckan kring 48 ms (-20 %)
    for days_ago in range(28, 7, -1):
        db_session.add(
            BodyMetric(
                user_id=known_user.id,
                metric="hrv",
                measured_at=now - timedelta(days=days_ago),
                source="apple_health",
                value=60,
            )
        )
    for days_ago in range(7, 0, -1):
        db_session.add(
            BodyMetric(
                user_id=known_user.id,
                metric="hrv",
                measured_at=now - timedelta(days=days_ago),
                source="apple_health",
                value=48,
            )
        )
    # Kort sömn i natt: 5 h
    db_session.add(
        SleepSession(
            user_id=known_user.id,
            start_at=now - timedelta(hours=13),
            end_at=now - timedelta(hours=8),
            source="apple_health",
        )
    )
    await db_session.commit()

    result = (
        await client.get("/api/ai/readiness", headers=auth(make_token))
    ).json()
    assert result["status"] == "red"
    statuses = {f["name"]: f["status"] for f in result["factors"]}
    assert statuses["HRV"] == "red"
    assert statuses["Sömn"] == "red"
    assert "vila" in result["recommendation"].lower()
