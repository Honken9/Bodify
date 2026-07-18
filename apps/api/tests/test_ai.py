import io
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.ai import ollama
from app.auth import ACCESS_JWT_HEADER
from app.models import BodyMetric, SleepSession


def auth(make_token, email="daniel@example.com"):
    return {ACCESS_JWT_HEADER: make_token(email=email)}


# Minimal men äkta JPEG-signatur — innehållet magic-byte-valideras numera.
FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32


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
        files={"file": ("gym.jpg", io.BytesIO(FAKE_JPEG), "image/jpeg")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["equipment"] == ["skivstång"]  # okänt ord filtreras
    names = [e["name"] for e in body["exercises"]]
    assert "Knäböj" in names and "Bänkpress" in names
    assert "Hantelrodd" not in names  # kräver hantlar


MEAL_PHOTO_RESPONSE = {
    "items": [
        {
            "name": "Grillad kycklingfilé",
            "grams": 150,
            "kcal_per_100g": 110,
            "protein_g_per_100g": 23,
            "carbs_g_per_100g": 0,
            "fat_g_per_100g": 2,
        },
        {
            "name": "Jasminris kokt",
            "grams": 200,
            "kcal_per_100g": 130,
            "protein_g_per_100g": 2.7,
            "carbs_g_per_100g": 28,
            "fat_g_per_100g": 0.3,
        },
    ]
}


async def test_meal_vision_returns_items(client, make_token, known_user, monkeypatch):
    async def fake_chat(prompt, **kwargs):
        assert kwargs.get("images_b64")
        return json.dumps(MEAL_PHOTO_RESPONSE)

    monkeypatch.setattr(ollama, "chat", fake_chat)
    resp = await client.post(
        "/api/ai/meal-vision",
        headers=auth(make_token),
        files={"file": ("mat.jpg", io.BytesIO(FAKE_JPEG), "image/jpeg")},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items[0]["name"] == "Grillad kycklingfilé"
    assert items[0]["grams"] == 150
    assert items[0]["per_100g"]["kcal"] == 110


async def test_meal_vision_ollama_down(client, make_token, known_user, monkeypatch):
    async def fake_chat(prompt, **kwargs):
        raise ollama.AIUnavailable("nere")

    monkeypatch.setattr(ollama, "chat", fake_chat)
    resp = await client.post(
        "/api/ai/meal-vision",
        headers=auth(make_token),
        files={"file": ("mat.jpg", io.BytesIO(FAKE_JPEG), "image/jpeg")},
    )
    assert resp.status_code == 503


async def test_photo_log_creates_entries_and_reuses_foods(
    client, make_token, known_user, monkeypatch
):
    from app.integrations import openfoodfacts

    async def no_remote(query, limit=10):
        return []

    monkeypatch.setattr(openfoodfacts, "search_products", no_remote)
    payload = {
        "eaten_on": "2026-07-16",
        "meal": "lunch",
        "items": [
            {
                "name": "Grillad kycklingfilé",
                "grams": 150,
                "per_100g": {"kcal": 110, "protein_g": 23, "carbs_g": 0, "fat_g": 2},
            },
            {
                "name": "Jasminris kokt",
                "grams": 200,
                "per_100g": {"kcal": 130, "protein_g": 2.7, "carbs_g": 28, "fat_g": 0.3},
            },
        ],
    }
    resp = await client.post(
        "/api/meals/photo-log", headers=auth(make_token), json=payload
    )
    assert resp.status_code == 200
    entries = resp.json()
    # 150 g × 110 kcal/100 g = 165 kcal; 200 g × 130 = 260 kcal
    by_name = {e["food_item"]["name"]: e for e in entries}
    assert by_name["Grillad kycklingfilé"]["kcal"] == 165.0
    assert by_name["Grillad kycklingfilé"]["protein_g"] == 34.5
    assert by_name["Jasminris kokt"]["kcal"] == 260.0

    # Dagstotalen stämmer
    day = (
        await client.get("/api/meals?day=2026-07-16", headers=auth(make_token))
    ).json()
    assert day["totals"]["kcal"] == 425.0

    # Samma rätt igen → livsmedlen återanvänds (inga dubbletter i biblioteket)
    await client.post("/api/meals/photo-log", headers=auth(make_token), json=payload)
    foods = (
        await client.get("/api/food/search?q=kycklingfilé", headers=auth(make_token))
    ).json()
    assert len(foods) == 1


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


async def test_meal_vision_applies_personal_calibration(
    client, make_token, known_user, db_session, monkeypatch
):
    # Användaren brukar halvera AI:ns gissningar → median 0.8 ska skala ner
    known_user.profile = {"portion_ratios": [0.8, 0.75, 0.8, 0.85, 0.8]}
    db_session.add(known_user)
    await db_session.commit()

    async def fake_chat(prompt, **kwargs):
        return json.dumps(
            {
                "items": [
                    {
                        "name": "Jasminris kokt",
                        "grams": 200,
                        "kcal_per_100g": 130,
                        "protein_g_per_100g": 2.7,
                        "carbs_g_per_100g": 28,
                        "fat_g_per_100g": 0.3,
                    }
                ]
            }
        )

    monkeypatch.setattr(ollama, "chat", fake_chat)
    resp = await client.post(
        "/api/ai/meal-vision",
        headers=auth(make_token),
        files={"file": ("mat.jpg", io.BytesIO(FAKE_JPEG), "image/jpeg")},
    )
    body = resp.json()
    assert body["calibrated"] is True
    assert body["factor"] == 0.8
    assert body["items"][0]["grams"] == 160  # 200 × 0.8


async def test_photo_log_records_calibration_ratios(
    client, make_token, known_user, monkeypatch
):
    from app.integrations import openfoodfacts

    async def no_remote(query, limit=10):
        return []

    monkeypatch.setattr(openfoodfacts, "search_products", no_remote)
    payload = {
        "eaten_on": "2026-07-18",
        "meal": "lunch",
        "items": [
            {
                "name": "Ris",
                "grams": 150,  # justerat ner från AI:ns 200
                "ai_grams": 200,
                "per_100g": {"kcal": 130, "protein_g": 2.7, "carbs_g": 28, "fat_g": 0.3},
            },
            {
                "name": "Kyckling",
                "grams": 500,  # orimlig kvot (>3×) ska INTE sparas
                "ai_grams": 100,
                "per_100g": {"kcal": 110, "protein_g": 23, "carbs_g": 0, "fat_g": 2},
            },
        ],
    }
    resp = await client.post(
        "/api/meals/photo-log", headers=auth(make_token), json=payload
    )
    assert resp.status_code == 200

    me = (await client.get("/api/me", headers=auth(make_token))).json()
    assert me["profile"]["portion_ratios"] == [0.75]
