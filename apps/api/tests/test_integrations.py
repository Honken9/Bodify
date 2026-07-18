from datetime import datetime, timedelta, timezone

import pytest


def test_withings_normalize_workouts():
    from app.integrations.withings import normalize_workouts

    series = [
        {
            "id": 12345,
            "category": 2,  # löpning
            "startdate": 1752730000,
            "enddate": 1752731560,  # 26 min
            "data": {
                "distance": 4000,
                "calories": 320,
                "hr_average": 152,
                "hr_max": 178,
            },
        },
        {
            "id": 12346,
            "category": 16,  # styrketräning
            "startdate": 1752800000,
            "enddate": 1752803600,
            "data": {"calories": 250},
        },
        {
            "id": 12347,
            "category": 9999,  # okänd kategori → other
            "startdate": 1752810000,
            "enddate": 1752811800,
            "data": {},
        },
    ]
    runs, gym, unknown = normalize_workouts(series)

    assert runs["type"] == "run"
    assert runs["name"] == "Löpning"
    assert runs["external_id"] == "12345"
    assert runs["duration_s"] == 1560
    assert runs["distance_m"] == 4000.0
    assert runs["avg_pace_s_per_km"] == 390.0  # 6:30 min/km
    assert runs["avg_hr"] == 152

    assert gym["type"] == "other"
    assert gym["name"] == "Styrketräning"
    assert gym["distance_m"] is None
    assert gym["avg_pace_s_per_km"] is None

    assert unknown["type"] == "other"
    assert unknown["name"] == "Träning"

from app.auth import ACCESS_JWT_HEADER
from app.integrations import strava as strava_mod
from app.integrations import withings as withings_mod
from app.models import OAuthConnection
from app.security import encrypt


def auth(make_token, email="daniel@example.com"):
    return {ACCESS_JWT_HEADER: make_token(email=email)}


@pytest.fixture
async def strava_conn(db_session, known_user) -> OAuthConnection:
    conn = OAuthConnection(
        user_id=known_user.id,
        provider="strava",
        access_token_enc=encrypt("access"),
        refresh_token_enc=encrypt("refresh"),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        external_user_id="4242",
    )
    db_session.add(conn)
    await db_session.commit()
    return conn


@pytest.fixture
async def withings_conn(db_session, known_user) -> OAuthConnection:
    conn = OAuthConnection(
        user_id=known_user.id,
        provider="withings",
        access_token_enc=encrypt("access"),
        refresh_token_enc=encrypt("refresh"),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        external_user_id="w-99",
    )
    db_session.add(conn)
    await db_session.commit()
    return conn


STRAVA_ACTIVITY = {
    "id": 1234567,
    "name": "Morgonrunda",
    "sport_type": "Run",
    "start_date": "2026-07-11T05:30:00Z",
    "moving_time": 2700,
    "elapsed_time": 2760,
    "distance": 10000.0,
    "average_heartrate": 156.0,
    "max_heartrate": 172.0,
    "calories": 650.0,
}


async def test_strava_webhook_verification(client):
    resp = await client.get(
        "/api/webhooks/strava",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "bodify-strava",
            "hub.challenge": "abc123",
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"hub.challenge": "abc123"}

    bad = await client.get(
        "/api/webhooks/strava",
        params={"hub.verify_token": "fel", "hub.challenge": "x"},
    )
    assert bad.status_code == 403


async def test_strava_event_creates_activity(
    client, make_token, known_user, strava_conn, monkeypatch
):
    async def fake_fetch(conn, db, activity_id):
        assert activity_id == "1234567"
        return dict(STRAVA_ACTIVITY)

    monkeypatch.setattr(strava_mod, "fetch_activity", fake_fetch)

    event = {
        "object_type": "activity",
        "aspect_type": "create",
        "owner_id": 4242,
        "object_id": 1234567,
    }
    resp = await client.post("/api/webhooks/strava", json=event)
    assert resp.status_code == 200

    activities = (
        await client.get("/api/cardio", headers=auth(make_token))
    ).json()
    [activity] = activities
    assert activity["type"] == "run"
    assert activity["distance_m"] == 10000.0
    # 2700 s / 10 km = 270 s/km = 4:30 min/km
    assert activity["avg_pace_s_per_km"] == 270.0

    # Samma event igen → uppdatering, ingen dubblett
    await client.post("/api/webhooks/strava", json=event)
    assert len((await client.get("/api/cardio", headers=auth(make_token))).json()) == 1


async def test_withings_event_stores_metrics(
    client, make_token, known_user, withings_conn, monkeypatch
):
    async def fake_measures(conn, db, startdate=None, enddate=None):
        ts = datetime(2026, 7, 12, 6, 0, tzinfo=timezone.utc)
        return [
            {"metric": "weight", "measured_at": ts, "value": 82.45},
            {"metric": "fat_percent", "measured_at": ts, "value": 14.2},
            {"metric": "pwv", "measured_at": ts, "value": 7.8},
        ]

    monkeypatch.setattr(withings_mod, "fetch_measures", fake_measures)

    resp = await client.post(
        "/api/webhooks/withings",
        data={"userid": "w-99", "appli": "1", "startdate": "1", "enddate": "2"},
    )
    assert resp.status_code == 200
    assert resp.json()["measures"] == 3

    latest = (
        await client.get("/api/metrics/latest", headers=auth(make_token))
    ).json()
    assert latest["weight"]["value"] == 82.45
    assert latest["fat_percent"]["value"] == 14.2
    assert latest["pwv"]["value"] == 7.8

    # Idempotent: samma notis igen ger inga dubbletter
    await client.post(
        "/api/webhooks/withings", data={"userid": "w-99", "appli": "1"}
    )
    series = (
        await client.get("/api/metrics/weight?days=30", headers=auth(make_token))
    ).json()
    assert len(series) == 1


async def test_withings_activity_event_stores_workouts_and_steps(
    client, make_token, known_user, withings_conn, monkeypatch
):
    async def fake_workouts(conn, db, days_back=7):
        return [
            {
                "external_id": "w-run-1",
                "type": "run",
                "name": "Löpning",
                "started_at": datetime(2026, 7, 17, 6, 15, tzinfo=timezone.utc),
                "duration_s": 1560,
                "distance_m": 4000.0,
                "calories": 320,
                "avg_hr": 152,
                "max_hr": 178,
                "avg_pace_s_per_km": 390.0,
            }
        ]

    async def fake_steps(conn, db, days_back=7):
        return [
            {
                "measured_at": datetime(2026, 7, 17, tzinfo=timezone.utc),
                "steps": 9450.0,
                "hr_average": 71.0,
                "hr_min": 48.0,
                "hr_max": 178.0,
            }
        ]

    monkeypatch.setattr(withings_mod, "fetch_workouts", fake_workouts)
    monkeypatch.setattr(withings_mod, "fetch_daily_activity", fake_steps)

    resp = await client.post(
        "/api/webhooks/withings", data={"userid": "w-99", "appli": "16"}
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "workouts": 1, "step_days": 1}

    cardio = (await client.get("/api/cardio", headers=auth(make_token))).json()
    assert len(cardio) == 1
    assert cardio[0]["type"] == "run"
    assert cardio[0]["source"] == "withings"
    assert cardio[0]["distance_m"] == 4000.0

    latest = (
        await client.get("/api/metrics/latest", headers=auth(make_token))
    ).json()
    assert latest["steps"]["value"] == 9450.0
    assert latest["steps"]["source"] == "withings"
    assert latest["hr_avg"]["value"] == 71.0
    assert latest["hr_min"]["value"] == 48.0
    assert latest["hr_max"]["value"] == 178.0

    # Samma notis igen → uppdatering, inga dubbletter
    await client.post(
        "/api/webhooks/withings", data={"userid": "w-99", "appli": "16"}
    )
    cardio = (await client.get("/api/cardio", headers=auth(make_token))).json()
    assert len(cardio) == 1


async def test_metric_series_windowed(client, make_token, known_user):
    for day, value in [("2026-07-10", 84.0), ("2026-07-15", 83.2), ("2026-07-17", 82.9)]:
        await client.post(
            "/api/metrics",
            headers=auth(make_token),
            json={
                "metric": "weight",
                "value": value,
                "measured_at": f"{day}T07:00:00Z",
            },
        )

    # Veckofönster 13–19 juli → två mätningar
    window = (
        await client.get(
            "/api/metrics/weight?start=2026-07-13&end=2026-07-19",
            headers=auth(make_token),
        )
    ).json()
    assert [p["value"] for p in window] == [83.2, 82.9]

    # Dagfönster → exakt en
    day = (
        await client.get(
            "/api/metrics/weight?start=2026-07-15&end=2026-07-15",
            headers=auth(make_token),
        )
    ).json()
    assert [p["value"] for p in day] == [83.2]


async def test_cardio_geo_only_returns_activities_with_gps(
    client, make_token, known_user, db_session
):
    from app.models import CardioActivity

    db_session.add(
        CardioActivity(
            user_id=known_user.id,
            type="run",
            source="strava",
            external_id="geo-1",
            name="Morgonrunda",
            started_at=datetime(2026, 7, 17, 6, 15, tzinfo=timezone.utc),
            duration_s=1560,
            distance_m=4000,
            raw={"polyline": "_p~iF~ps|U_ulLnnqC", "start_latlng": [59.33, 18.06]},
        )
    )
    db_session.add(
        CardioActivity(
            user_id=known_user.id,
            type="other",
            source="manual",
            external_id=None,
            name="Padel",
            started_at=datetime(2026, 7, 16, 18, 0, tzinfo=timezone.utc),
            duration_s=3600,
            raw=None,  # ingen GPS → ska inte med på kartan
        )
    )
    await db_session.commit()

    geo = (await client.get("/api/cardio/geo", headers=auth(make_token))).json()
    assert len(geo) == 1
    assert geo[0]["name"] == "Morgonrunda"
    assert geo[0]["polyline"] == "_p~iF~ps|U_ulLnnqC"
    assert geo[0]["start"] == [59.33, 18.06]


def test_strava_normalize_keeps_gps():
    from app.integrations.strava import normalize_activity

    fields = normalize_activity(
        {
            "id": 987,
            "type": "Run",
            "name": "Kvällsrunda",
            "start_date": "2026-07-17T18:00:00Z",
            "moving_time": 1800,
            "distance": 5000,
            "map": {"summary_polyline": "abc123"},
            "start_latlng": [59.31, 18.07],
        }
    )
    assert fields["raw"]["polyline"] == "abc123"
    assert fields["raw"]["start_latlng"] == [59.31, 18.07]


HAE_PAYLOAD = {
    "data": {
        "metrics": [
            {
                "name": "heart_rate_variability",
                "units": "ms",
                "data": [{"date": "2026-07-12 07:00:00 +0200", "qty": 58.5}],
            },
            {
                "name": "step_count",
                "units": "count",
                "data": [{"date": "2026-07-11 23:59:00 +0200", "qty": 9450}],
            },
            {
                "name": "sleep_analysis",
                "data": [
                    {
                        "sleepStart": "2026-07-11 23:10:00 +0200",
                        "sleepEnd": "2026-07-12 06:45:00 +0200",
                        "deep": 1.2,
                        "rem": 1.8,
                        "core": 4.1,
                        "awake": 0.4,
                    }
                ],
            },
        ],
        "workouts": [
            {
                "name": "Outdoor Run",
                "start": "2026-07-11 05:31:00 +0200",
                "end": "2026-07-11 06:16:00 +0200",
                "distance": {"qty": 9.98, "units": "km"},
                "activeEnergyBurned": {"qty": 640, "units": "kcal"},
                "avgHeartRate": {"qty": 155, "units": "bpm"},
            }
        ],
    }
}


async def test_apple_health_requires_token(client):
    resp = await client.post("/api/webhooks/apple-health", json=HAE_PAYLOAD)
    assert resp.status_code == 401

    resp = await client.post(
        "/api/webhooks/apple-health",
        json=HAE_PAYLOAD,
        headers={"Authorization": "Bearer fel-token"},
    )
    assert resp.status_code == 401


async def test_apple_health_ingest(client, make_token, known_user):
    created = (
        await client.post(
            "/api/integrations/apple-health/tokens",
            headers=auth(make_token),
            json={"label": "Daniels iPhone"},
        )
    ).json()
    token = created["token"]

    resp = await client.post(
        "/api/webhooks/apple-health",
        json=HAE_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["metrics"] == 2
    assert body["sleep"] == 1
    assert body["workouts"] == 1

    latest = (
        await client.get("/api/metrics/latest", headers=auth(make_token))
    ).json()
    assert latest["hrv"]["value"] == 58.5
    assert latest["steps"]["value"] == 9450

    # Ny sändning av samma data är idempotent
    resp2 = await client.post(
        "/api/webhooks/apple-health",
        json=HAE_PAYLOAD,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.json()["sleep"] == 0
    assert resp2.json()["workouts"] == 0


def test_encode_polyline_google_example():
    from app.integrations.apple_health import encode_polyline

    # Googles referensexempel för polyline-kodning
    points = [(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]
    assert encode_polyline(points) == "_p~iF~ps|U_ulLnnqC_mqNvxq`@"


async def test_apple_workout_route_and_fun_metrics(client, make_token, known_user):
    token = (
        await client.post(
            "/api/integrations/apple-health/tokens",
            headers=auth(make_token),
            json={},
        )
    ).json()["token"]

    payload = {
        "data": {
            "metrics": [
                {
                    "name": "flights_climbed",
                    "units": "count",
                    "data": [{"date": "2026-07-18 12:00:00 +0200", "qty": 14}],
                },
                {
                    "name": "apple_exercise_time",
                    "units": "min",
                    "data": [{"date": "2026-07-18 12:00:00 +0200", "qty": 42}],
                },
                {
                    "name": "active_energy",
                    "units": "kJ",  # skalas till kcal
                    "data": [{"date": "2026-07-18 12:00:00 +0200", "qty": 2000}],
                },
                {
                    "name": "blood_oxygen_saturation",
                    "units": "%",
                    "data": [{"date": "2026-07-18 12:00:00 +0200", "qty": 97}],
                },
            ],
            "workouts": [
                {
                    "name": "Outdoor Walk",
                    "start": "2026-07-18 08:00:00 +0000",
                    "end": "2026-07-18 08:45:00 +0000",
                    "distance": {"qty": 3.4, "units": "km"},
                    "elevation": {"ascent": 38, "descent": 32, "units": "m"},
                    "temperature": {"qty": 18.4, "units": "degC"},
                    "route": [
                        {"lat": 59.243, "lon": 18.088, "altitude": 30},
                        {"lat": 59.245, "lon": 18.091, "altitude": 31},
                        {"lat": 59.248, "lon": 18.095, "altitude": 33},
                    ],
                }
            ],
        }
    }
    resp = await client.post(
        "/api/webhooks/apple-health",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["workouts"] == 1
    assert resp.json()["metrics"] == 4

    latest = (
        await client.get("/api/metrics/latest", headers=auth(make_token))
    ).json()
    assert latest["flights_climbed"]["value"] == 14
    assert latest["exercise_min"]["value"] == 42
    assert latest["active_kcal"]["value"] == round(2000 * 0.2390057, 3)
    assert latest["spo2"]["value"] == 97

    # Promenadens GPS-rutt hamnar på kartan som linje
    geo = (await client.get("/api/cardio/geo", headers=auth(make_token))).json()
    assert len(geo) == 1
    assert geo[0]["type"] == "walk"
    assert geo[0]["polyline"]
    assert geo[0]["start"] == [59.243, 18.088]


async def test_apple_route_enriches_gps_less_twin(
    client, make_token, known_user, db_session
):
    from app.models import CardioActivity

    # Withings-promenaden finns redan — utan GPS
    walk = CardioActivity(
        user_id=known_user.id,
        type="walk",
        source="withings",
        external_id="w-walk-1",
        name="Promenad",
        started_at=datetime(2026, 7, 18, 8, 2, tzinfo=timezone.utc),
        duration_s=2700,
        distance_m=3400.0,
    )
    db_session.add(walk)
    await db_session.commit()

    token = (
        await client.post(
            "/api/integrations/apple-health/tokens",
            headers=auth(make_token),
            json={},
        )
    ).json()["token"]

    payload = {
        "data": {
            "workouts": [
                {
                    "name": "Outdoor Walk",
                    "start": "2026-07-18 08:00:00 +0000",
                    "end": "2026-07-18 08:45:00 +0000",
                    "route": [
                        {"lat": 59.243, "lon": 18.088},
                        {"lat": 59.246, "lon": 18.092},
                    ],
                }
            ]
        }
    }
    resp = await client.post(
        "/api/webhooks/apple-health",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.json()["workouts"] == 0  # ingen dubblett skapas…

    # …men Withings-passet fick Apples GPS-rutt
    geo = (await client.get("/api/cardio/geo", headers=auth(make_token))).json()
    assert len(geo) == 1
    assert geo[0]["id"] == str(walk.id)
    assert geo[0]["polyline"]


async def test_apple_workout_deduped_against_strava(
    client, make_token, known_user, strava_conn, monkeypatch
):
    async def fake_fetch(conn, db, activity_id):
        return dict(STRAVA_ACTIVITY)

    monkeypatch.setattr(strava_mod, "fetch_activity", fake_fetch)
    await client.post(
        "/api/webhooks/strava",
        json={
            "object_type": "activity",
            "aspect_type": "create",
            "owner_id": 4242,
            "object_id": 1234567,
        },
    )

    token = (
        await client.post(
            "/api/integrations/apple-health/tokens",
            headers=auth(make_token),
            json={},
        )
    ).json()["token"]

    # HAE-passet startar 05:31 lokal (+0200) = 03:31 UTC… justera till
    # samma tid som Strava-passet (05:30 UTC) för överlapp
    payload = {
        "data": {
            "workouts": [
                {
                    "name": "Outdoor Run",
                    "start": "2026-07-11 05:35:00 +0000",
                    "end": "2026-07-11 06:20:00 +0000",
                    "distance": {"qty": 10.0, "units": "km"},
                }
            ]
        }
    }
    resp = await client.post(
        "/api/webhooks/apple-health",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.json()["workouts"] == 0  # dubblett mot Strava hoppas över

    activities = (
        await client.get("/api/cardio", headers=auth(make_token))
    ).json()
    assert len(activities) == 1
    assert activities[0]["source"] == "strava"


async def test_goal_body_metric_progress(client, make_token, known_user):
    headers = auth(make_token)
    # Startvikt/fett: 18 % → mål 11 %
    await client.post(
        "/api/metrics",
        headers=headers,
        json={"metric": "fat_percent", "value": 18.0},
    )
    goal = (
        await client.post(
            "/api/goals",
            headers=headers,
            json={
                "kind": "body_metric",
                "title": "Ner till 11 % kroppsfett",
                "target": {"metric": "fat_percent", "value": 11.0},
            },
        )
    ).json()
    assert goal["target"]["baseline"] == 18.0
    assert goal["progress"] == 0.0

    # Halvvägs: 14.5 %
    await client.post(
        "/api/metrics",
        headers=headers,
        json={"metric": "fat_percent", "value": 14.5},
    )
    [g] = (await client.get("/api/goals", headers=headers)).json()
    assert g["progress"] == 0.5
    assert g["current"]["current_value"] == 14.5


async def test_goal_pace_distance_progress(
    client, make_token, known_user, strava_conn, monkeypatch
):
    async def fake_fetch(conn, db, activity_id):
        return dict(STRAVA_ACTIVITY)  # 10 km på 45:00 → exakt målet

    monkeypatch.setattr(strava_mod, "fetch_activity", fake_fetch)
    await client.post(
        "/api/webhooks/strava",
        json={
            "object_type": "activity",
            "aspect_type": "create",
            "owner_id": 4242,
            "object_id": 1234567,
        },
    )

    goal = (
        await client.post(
            "/api/goals",
            headers=auth(make_token),
            json={
                "kind": "pace_distance",
                "title": "10 km på 45 minuter",
                "target": {"distance_m": 10000, "time_s": 2700},
            },
        )
    ).json()
    assert goal["progress"] == 1.0
    assert goal["current"]["best_time_s"] == 2700
    assert goal["achieved_at"] is not None


async def test_integrations_status_and_isolation(
    client, make_token, known_user, other_user, strava_conn
):
    status = (
        await client.get("/api/integrations", headers=auth(make_token))
    ).json()
    strava_status = next(
        p for p in status["providers"] if p["provider"] == "strava"
    )
    assert strava_status["connected"] is True

    anna = (
        await client.get(
            "/api/integrations", headers=auth(make_token, "anna@example.com")
        )
    ).json()
    assert all(p["connected"] is False for p in anna["providers"])


async def test_strava_backfill_paginates_and_dedupes(
    client, make_token, known_user, db_session, monkeypatch
):
    from app.integrations import strava as strava_mod
    from app.models import OAuthConnection
    from app.security import encrypt

    conn = OAuthConnection(
        user_id=known_user.id,
        provider="strava",
        access_token_enc=encrypt("token"),
        refresh_token_enc=encrypt("refresh"),
        external_user_id="ath-1",
    )
    db_session.add(conn)
    await db_session.commit()

    def act(i, with_map=True):
        return {
            "id": i,
            "type": "Run",
            "name": f"Runda {i}",
            "start_date": "2026-07-10T06:00:00Z",
            "moving_time": 1800,
            "distance": 5000,
            "map": {"summary_polyline": "poly"} if with_map else {},
            "start_latlng": [59.3, 18.1] if with_map else None,
        }

    # Full första sida (200 st) → hämtar vidare; kort andra sida → stopp
    pages = {
        1: [act(i) for i in range(1, 201)],
        2: [act(201, with_map=False)],
    }

    async def fake_page(c, db, page, per_page=200):
        return pages.get(page, [])

    monkeypatch.setattr(strava_mod, "fetch_activity_page", fake_page)

    resp = await client.post(
        "/api/integrations/strava/sync", headers=auth(make_token)
    )
    assert resp.status_code == 200
    assert resp.json()["imported"] == 201

    # Kartan får bara de med GPS
    geo = (
        await client.get("/api/cardio/geo?limit=500", headers=auth(make_token))
    ).json()
    assert len(geo) == 200

    # Körs igen → inga dubbletter, inget nytt importerat
    resp = await client.post(
        "/api/integrations/strava/sync", headers=auth(make_token)
    )
    assert resp.json()["imported"] == 0
    geo = (
        await client.get("/api/cardio/geo?limit=500", headers=auth(make_token))
    ).json()
    assert len(geo) == 200  # oförändrat — inga dubbletter skapades


async def test_strava_sync_requires_connection(client, make_token, known_user):
    resp = await client.post(
        "/api/integrations/strava/sync", headers=auth(make_token)
    )
    assert resp.status_code == 404


async def test_manual_location_puts_activity_on_map(
    client, make_token, known_user, db_session
):
    from app.models import CardioActivity

    gym = CardioActivity(
        user_id=known_user.id,
        type="other",
        source="withings",
        external_id="gym-1",
        name="Styrketräning",
        started_at=datetime(2026, 7, 16, 17, 0, tzinfo=timezone.utc),
        duration_s=3600,
    )
    db_session.add(gym)
    await db_session.commit()

    # Utan plats → inte på kartan
    geo = (await client.get("/api/cardio/geo", headers=auth(make_token))).json()
    assert geo == []

    resp = await client.patch(
        f"/api/cardio/{gym.id}/location",
        headers=auth(make_token),
        json={"lat": 59.332, "lng": 18.015},
    )
    assert resp.status_code == 200
    assert resp.json()["start"] == [59.332, 18.015]

    geo = (await client.get("/api/cardio/geo", headers=auth(make_token))).json()
    assert len(geo) == 1
    assert geo[0]["start"] == [59.332, 18.015]

    # Någon annans pass går inte att platssätta
    anna = auth(make_token, "anna@example.com")
    from app.models import User
    from sqlalchemy import select

    if await db_session.scalar(select(User).where(User.email == "anna@example.com")) is None:
        db_session.add(User(email="anna@example.com"))
        await db_session.commit()
    denied = await client.patch(
        f"/api/cardio/{gym.id}/location",
        headers=anna,
        json={"lat": 1, "lng": 1},
    )
    assert denied.status_code == 404


async def test_bulk_location(client, make_token, known_user, db_session):
    from app.models import CardioActivity

    def gym(n, raw=None):
        return CardioActivity(
            user_id=known_user.id,
            type="other",
            source="withings",
            external_id=f"bulk-{n}",
            name=f"Pass {n}",
            started_at=datetime(2026, 7, 10 + n, 17, 0, tzinfo=timezone.utc),
            duration_s=3600,
            raw=raw,
        )

    a = gym(1)  # utan plats — ska platssättas via ids
    b = gym(2)  # utan plats — ska platssättas via all_missing
    c = gym(3, raw={"polyline": "abc", "start_latlng": [59.0, 18.0]})  # GPS-rutt — rörs ej
    d = gym(4, raw={"start_latlng": [57.7, 11.9], "location_source": "manual"})  # redan satt
    db_session.add_all([a, b, c, d])
    await db_session.commit()

    # Varken ids eller all_missing → fel
    resp = await client.patch(
        "/api/cardio/location-bulk",
        headers=auth(make_token),
        json={"lat": 59.243, "lng": 18.088},
    )
    assert resp.status_code == 400

    # Valda id:n platssätts (SATS Farsta)
    resp = await client.patch(
        "/api/cardio/location-bulk",
        headers=auth(make_token),
        json={"lat": 59.243, "lng": 18.088, "ids": [str(a.id), str(c.id)]},
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 1  # c skyddas av sin GPS-rutt

    # "Alla som saknar plats" → bara b; d:s manuella plats skrivs inte över
    resp = await client.patch(
        "/api/cardio/location-bulk",
        headers=auth(make_token),
        json={"lat": 59.336, "lng": 18.071, "all_missing": True},
    )
    assert resp.json()["updated"] == 1

    geo = {
        g["name"]: g["start"]
        for g in (
            await client.get("/api/cardio/geo", headers=auth(make_token))
        ).json()
    }
    assert geo["Pass 1"] == [59.243, 18.088]
    assert geo["Pass 2"] == [59.336, 18.071]
    assert geo["Pass 4"] == [57.7, 11.9]

    # Någon annans pass kan inte bulk-platssättas
    anna = auth(make_token, "anna2@example.com")
    from app.models import User
    from sqlalchemy import select

    if await db_session.scalar(select(User).where(User.email == "anna2@example.com")) is None:
        db_session.add(User(email="anna2@example.com"))
        await db_session.commit()
    resp = await client.patch(
        "/api/cardio/location-bulk",
        headers=anna,
        json={"lat": 1, "lng": 1, "ids": [str(b.id)]},
    )
    assert resp.json()["updated"] == 0


def test_strava_normalize_splits():
    from app.integrations.strava import normalize_activity

    detail = {
        "id": 555,
        "sport_type": "Run",
        "start_date": "2026-07-13T06:00:00Z",
        "moving_time": 1800,
        "distance": 5000.0,
        "splits_metric": [
            {
                "split": 1,
                "distance": 1000.0,
                "moving_time": 330,
                "average_heartrate": 148.6,
                "elevation_difference": 4.2,
            },
            {"split": 2, "distance": 1000.0, "moving_time": 350},
            {"split": 3, "distance": 120.0, "moving_time": 40},
            {"split": 4, "distance": 0, "moving_time": 0},  # skräp filtreras
        ],
    }
    splits = normalize_activity(detail)["raw"]["splits"]
    assert len(splits) == 3
    assert splits[0] == {
        "km": 1,
        "distance_m": 1000,
        "time_s": 330,
        "pace_s_per_km": 330.0,
        "hr": 149,
        "elev_diff_m": 4.2,
    }
    assert splits[1]["hr"] is None

    # Listsvar (utan splits_metric) → ingen splits-nyckel = "okänt, hämta vid behov"
    summary = {"id": 556, "sport_type": "Run", "start_date": "2026-07-13T06:00:00Z"}
    assert "splits" not in normalize_activity(summary)["raw"]


async def test_watch_gym_pass_merges_with_logged_session(
    client, make_token, known_user, withings_conn, db_session, monkeypatch
):
    from app.models import WorkoutSession

    ws = WorkoutSession(
        user_id=known_user.id,
        started_at=datetime(2026, 7, 18, 17, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 7, 18, 18, 5, tzinfo=timezone.utc),
        start_lat=59.243,
        start_lng=18.088,
    )
    db_session.add(ws)
    await db_session.commit()

    async def watch_gym(conn, db, days_back=7):
        return [
            {
                "external_id": "w-gym-18",
                "type": "other",
                "name": "Styrketräning",
                "started_at": datetime(2026, 7, 18, 17, 8, tzinfo=timezone.utc),
                "duration_s": 3300,
                "distance_m": None,
                "calories": 410,
                "avg_hr": 121,
                "max_hr": 158,
                "avg_pace_s_per_km": None,
            }
        ]

    async def no_days(conn, db, days_back=7):
        return []

    monkeypatch.setattr(withings_mod, "fetch_workouts", watch_gym)
    monkeypatch.setattr(withings_mod, "fetch_daily_activity", no_days)

    resp = await client.post(
        "/api/webhooks/withings", data={"userid": "w-99", "appli": "16"}
    )
    assert resp.status_code == 200

    # Klockpasset är ihopslaget → syns inte som eget pass
    cardio = (await client.get("/api/cardio", headers=auth(make_token))).json()
    assert cardio == []

    # ...men berikar styrkepasset med klockdata
    sessions = (await client.get("/api/sessions", headers=auth(make_token))).json()
    assert sessions[0]["watch"]["avg_hr"] == 121.0
    assert sessions[0]["watch"]["calories"] == 410.0
    assert sessions[0]["watch"]["source"] == "withings"

    # Gympasset med position syns på kartan som styrkepass
    geo = (await client.get("/api/cardio/geo", headers=auth(make_token))).json()
    strength = [g for g in geo if g["type"] == "strength"]
    assert len(strength) == 1
    assert strength[0]["start"] == [59.243, 18.088]

    # Koppla isär → eget pass igen, och länkas aldrig om automatiskt
    resp = await client.post(
        f"/api/sessions/{ws.id}/unlink-watch", headers=auth(make_token)
    )
    assert resp.status_code == 200
    assert resp.json()["watch"] is None
    cardio = (await client.get("/api/cardio", headers=auth(make_token))).json()
    assert len(cardio) == 1

    await client.post(
        "/api/webhooks/withings", data={"userid": "w-99", "appli": "16"}
    )
    sessions = (await client.get("/api/sessions", headers=auth(make_token))).json()
    assert sessions[0]["watch"] is None  # opt-out respekteras
    cardio = (await client.get("/api/cardio", headers=auth(make_token))).json()
    assert len(cardio) == 1


async def test_auto_merge_can_be_disabled(
    client, make_token, known_user, withings_conn, db_session, monkeypatch
):
    from app.models import WorkoutSession

    # Stäng av ihopslagning i profilen
    resp = await client.patch(
        "/api/me",
        headers=auth(make_token),
        json={"profile": {"auto_merge_watch": False}},
    )
    assert resp.json()["profile"]["auto_merge_watch"] is False

    ws = WorkoutSession(
        user_id=known_user.id,
        started_at=datetime(2026, 7, 19, 17, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 7, 19, 18, 0, tzinfo=timezone.utc),
    )
    db_session.add(ws)
    await db_session.commit()

    async def watch_gym(conn, db, days_back=7):
        return [
            {
                "external_id": "w-gym-19",
                "type": "other",
                "name": "Styrketräning",
                "started_at": datetime(2026, 7, 19, 17, 5, tzinfo=timezone.utc),
                "duration_s": 3000,
                "distance_m": None,
                "calories": 300,
                "avg_hr": 110,
                "max_hr": 150,
                "avg_pace_s_per_km": None,
            }
        ]

    async def no_days(conn, db, days_back=7):
        return []

    monkeypatch.setattr(withings_mod, "fetch_workouts", watch_gym)
    monkeypatch.setattr(withings_mod, "fetch_daily_activity", no_days)
    await client.post(
        "/api/webhooks/withings", data={"userid": "w-99", "appli": "16"}
    )

    # Ingen ihopslagning — klockpasset är kvar som eget
    cardio = (await client.get("/api/cardio", headers=auth(make_token))).json()
    assert len(cardio) == 1
    sessions = (await client.get("/api/sessions", headers=auth(make_token))).json()
    assert sessions[0]["watch"] is None


async def test_geo_search_short_query_returns_empty(client, make_token, known_user):
    # Under 2 tecken → tom lista utan att Nominatim anropas
    resp = await client.get("/api/cardio/geo-search?q=s", headers=auth(make_token))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_geo_search_proxies_nominatim(client, make_token, known_user, monkeypatch):
    import httpx

    real_get = httpx.AsyncClient.get

    async def fake_get(self, url, **kwargs):
        if "nominatim" not in str(url):
            return await real_get(self, url, **kwargs)  # testklientens egna anrop
        assert kwargs["params"]["q"] == "SATS Farsta"
        return httpx.Response(
            200,
            json=[
                {"display_name": "SATS Farsta, Stockholm", "lat": "59.243", "lon": "18.088"},
                {"display_name": "Utan koordinater"},
            ],
            request=httpx.Request("GET", str(url)),
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    resp = await client.get(
        "/api/cardio/geo-search?q=SATS%20Farsta", headers=auth(make_token)
    )
    assert resp.status_code == 200
    assert resp.json() == [
        {"name": "SATS Farsta, Stockholm", "lat": 59.243, "lng": 18.088}
    ]


async def test_withings_manual_sync(
    client, make_token, known_user, withings_conn, monkeypatch
):
    async def fake_measures(conn, db, startdate=None, enddate=None):
        assert startdate is not None  # bara senaste 30 dagarna hämtas
        return [
            {
                "metric": "weight",
                "measured_at": datetime(2026, 7, 18, 7, 0, tzinfo=timezone.utc),
                "value": 82.1,
            }
        ]

    async def fake_workouts(conn, db, days_back=7):
        return []

    async def fake_steps(conn, db, days_back=7):
        return [
            {
                "measured_at": datetime(2026, 7, 18, tzinfo=timezone.utc),
                "steps": 5200.0,
                "hr_average": 68.0,
                "hr_min": 52.0,
                "hr_max": 141.0,
            }
        ]

    async def fake_sleep(conn, db, days_back=7):
        return [
            {
                "start_at": datetime(2026, 7, 17, 21, 45, tzinfo=timezone.utc),
                "end_at": datetime(2026, 7, 18, 5, 30, tzinfo=timezone.utc),
                "deep_s": 5400,
                "light_s": 14400,
                "rem_s": 6300,
                "awake_s": 1200,
                "total_s": 26100,
                "score": 82,
            }
        ]

    monkeypatch.setattr(withings_mod, "fetch_measures", fake_measures)
    monkeypatch.setattr(withings_mod, "fetch_workouts", fake_workouts)
    monkeypatch.setattr(withings_mod, "fetch_daily_activity", fake_steps)
    monkeypatch.setattr(withings_mod, "fetch_sleep", fake_sleep)

    resp = await client.post(
        "/api/integrations/withings/sync", headers=auth(make_token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["measures"] == 1
    assert body["step_days"] == 1
    assert body["sleep_nights"] == 1

    latest = (
        await client.get("/api/metrics/latest", headers=auth(make_token))
    ).json()
    assert latest["weight"]["value"] == 82.1
    assert latest["steps"]["value"] == 5200.0
    assert latest["sleep_duration"]["value"] == 7.25  # 26 100 s
    assert latest["sleep_score"]["value"] == 82.0

    # Körs igen → uppdaterar samma natt, ingen dubblett
    resp = await client.post(
        "/api/integrations/withings/sync", headers=auth(make_token)
    )
    assert resp.json()["sleep_nights"] == 1


async def test_withings_sleep_webhook_appli_44(
    client, make_token, known_user, withings_conn, monkeypatch
):
    async def fake_sleep(conn, db, days_back=7):
        return [
            {
                "start_at": datetime(2026, 7, 16, 22, 0, tzinfo=timezone.utc),
                "end_at": datetime(2026, 7, 17, 6, 0, tzinfo=timezone.utc),
                "deep_s": 6000,
                "light_s": 15000,
                "rem_s": 5000,
                "awake_s": 900,
                "total_s": 26000,
                "score": None,  # äldre mätare saknar poäng — får inte krascha
            }
        ]

    monkeypatch.setattr(withings_mod, "fetch_sleep", fake_sleep)
    resp = await client.post(
        "/api/webhooks/withings", data={"userid": "w-99", "appli": "44"}
    )
    assert resp.status_code == 200
    assert resp.json()["sleep_nights"] == 1

    latest = (
        await client.get("/api/metrics/latest", headers=auth(make_token))
    ).json()
    assert latest["sleep_duration"]["value"] == 7.22
    assert "sleep_score" not in latest


async def test_withings_sync_requires_connection(client, make_token, known_user):
    resp = await client.post(
        "/api/integrations/withings/sync", headers=auth(make_token)
    )
    assert resp.status_code == 404


async def test_strava_wins_over_watch_duplicates(
    client, make_token, known_user, withings_conn, strava_conn, monkeypatch
):
    from app.models import CardioActivity

    run_start = datetime(2026, 7, 13, 7, 0, tzinfo=timezone.utc)

    # 1) Klockans GPS-lösa version finns redan (importerad via Withings)
    async def watch_workout(conn, db, days_back=7):
        return [
            {
                "external_id": "w-run-13",
                "type": "run",
                "name": "Löpning",
                "started_at": run_start + timedelta(minutes=3),
                "duration_s": 3300,
                "distance_m": 10300.0,
                "calories": 700,
                "avg_hr": 155,
                "max_hr": 175,
                "avg_pace_s_per_km": 320.0,
            }
        ]

    async def no_steps(conn, db, days_back=7):
        return []

    monkeypatch.setattr(withings_mod, "fetch_workouts", watch_workout)
    monkeypatch.setattr(withings_mod, "fetch_daily_activity", no_steps)
    await client.post(
        "/api/webhooks/withings", data={"userid": "w-99", "appli": "16"}
    )

    # 2) Strava-backfill hittar samma runda MED GPS → dubbletten rensas
    async def strava_page(c, db, page, per_page=200):
        if page > 1:
            return []
        return [
            {
                "id": 555,
                "type": "Run",
                "name": "Söndagsrunda 10,3 km",
                "start_date": "2026-07-13T07:00:00Z",
                "moving_time": 3300,
                "distance": 10300,
                "map": {"summary_polyline": "gpsdata"},
                "start_latlng": [59.33, 18.06],
            }
        ]

    monkeypatch.setattr(strava_mod, "fetch_activity_page", strava_page)
    await client.post("/api/integrations/strava/sync", headers=auth(make_token))

    cardio = (await client.get("/api/cardio", headers=auth(make_token))).json()
    assert len(cardio) == 1  # bara Strava-versionen kvar
    assert cardio[0]["source"] == "strava"

    geo = (await client.get("/api/cardio/geo", headers=auth(make_token))).json()
    assert len(geo) == 1 and geo[0]["polyline"] == "gpsdata"

    # 3) Kommer klockans version IGEN efteråt → hoppas över
    await client.post(
        "/api/webhooks/withings", data={"userid": "w-99", "appli": "16"}
    )
    cardio = (await client.get("/api/cardio", headers=auth(make_token))).json()
    assert len(cardio) == 1
