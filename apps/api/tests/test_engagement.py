import io
from datetime import datetime, timezone

from app.auth import ACCESS_JWT_HEADER

# Minimal giltig 1×1-px PNG
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63fcff9fa11e00078d027e8f5ea3f80000000049454e44ae426082"
)


def auth(make_token, email="daniel@example.com"):
    return {ACCESS_JWT_HEADER: make_token(email=email)}


async def test_photo_upload_list_and_isolation(
    client, make_token, known_user, other_user, tmp_path, monkeypatch
):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "data_dir", str(tmp_path))

    resp = await client.post(
        "/api/photos",
        headers=auth(make_token),
        files={"file": ("front.png", io.BytesIO(PNG_BYTES), "image/png")},
        data={"pose": "front"},
    )
    assert resp.status_code == 201
    photo = resp.json()

    photos = (await client.get("/api/photos", headers=auth(make_token))).json()
    assert len(photos) == 1

    file_resp = await client.get(
        f"/api/photos/{photo['id']}/file", headers=auth(make_token)
    )
    assert file_resp.status_code == 200
    assert file_resp.content == PNG_BYTES

    # Anna ser/når inte Daniels foton
    anna = auth(make_token, "anna@example.com")
    assert (await client.get("/api/photos", headers=anna)).json() == []
    assert (
        await client.get(f"/api/photos/{photo['id']}/file", headers=anna)
    ).status_code == 404

    # Radering tar bort både post och fil
    assert (
        await client.delete(f"/api/photos/{photo['id']}", headers=auth(make_token))
    ).status_code == 204
    assert (await client.get("/api/photos", headers=auth(make_token))).json() == []


async def test_photo_rejects_bad_type(client, make_token, known_user, tmp_path, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "data_dir", str(tmp_path))
    resp = await client.post(
        "/api/photos",
        headers=auth(make_token),
        files={"file": ("x.txt", io.BytesIO(b"hej"), "text/plain")},
    )
    assert resp.status_code == 400


async def test_push_subscription_roundtrip(client, make_token, known_user):
    sub = {
        "endpoint": "https://push.example.com/abc",
        "keys": {"p256dh": "nyckel", "auth": "hemlis"},
    }
    resp = await client.post(
        "/api/push/subscriptions", headers=auth(make_token), json=sub
    )
    assert resp.status_code == 201

    # Samma endpoint igen → uppdatering, inte dubblett
    resp2 = await client.post(
        "/api/push/subscriptions", headers=auth(make_token), json=sub
    )
    assert resp2.status_code == 201


async def test_vapid_key_unconfigured_503(client):
    resp = await client.get("/api/push/vapid-public-key")
    assert resp.status_code == 503


async def test_dashboard_aggregates(client, make_token, known_user):
    headers = auth(make_token)

    # Ett styrkepass med volym
    ex = (
        await client.post(
            "/api/exercises",
            headers=headers,
            json={"name": "Bänkpress", "muscle_groups": ["bröst"]},
        )
    ).json()
    session = (
        await client.post("/api/sessions/start", headers=headers, json={})
    ).json()
    await client.post(
        f"/api/sessions/{session['id']}/sets",
        headers=headers,
        json={"exercise_id": ex["id"], "weight_kg": 100, "reps": 10},
    )
    await client.post(
        f"/api/sessions/{session['id']}/finish", headers=headers, json={}
    )

    # En löprunda
    await client.post(
        "/api/cardio",
        headers=headers,
        json={
            "type": "run",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "duration_s": 2700,
            "distance_m": 10000,
        },
    )

    # Vikt i början och slutet av perioden
    from datetime import timedelta

    await client.post(
        "/api/metrics",
        headers=headers,
        json={
            "metric": "weight",
            "value": 84.0,
            "measured_at": (
                datetime.now(timezone.utc) - timedelta(days=5)
            ).isoformat(),
        },
    )
    await client.post(
        "/api/metrics", headers=headers, json={"metric": "weight", "value": 83.2}
    )

    dash = (await client.get("/api/dashboard?period=week", headers=headers)).json()
    assert dash["strength_sessions"] == 1
    assert dash["total_volume_kg"] == 1000
    assert dash["cardio_sessions"] == 1
    assert dash["cardio_distance_km"] == 10.0
    assert dash["weight_delta_kg"] == -0.8
    assert dash["active_days"] >= 1
    assert len(dash["activity"]) == 7
