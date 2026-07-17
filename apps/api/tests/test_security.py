"""Tester för säkerhetshårdningen: CSRF-origin-kontroll, rate limiting,
bildvalidering via magiska bytes och streckkodsvalidering."""

import io

import pytest

from app.auth import ACCESS_JWT_HEADER
from app.security import sniff_image


def auth(make_token, email="daniel@example.com"):
    return {ACCESS_JWT_HEADER: make_token(email=email)}


# ── Startvakter ───────────────────────────────────────────────


def test_startup_refuses_default_secret_in_production(monkeypatch):
    from app.config import get_settings
    from app.main import _startup_checks

    settings = get_settings()
    monkeypatch.setattr(settings, "cf_access_aud", "prod-aud")
    monkeypatch.setattr(settings, "secret_key", "dev-secret-change-me")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        _startup_checks()


def test_startup_refuses_dev_auth_in_production(monkeypatch):
    from app.config import get_settings
    from app.main import _startup_checks

    settings = get_settings()
    monkeypatch.setattr(settings, "cf_access_aud", "prod-aud")
    monkeypatch.setattr(settings, "secret_key", "a-long-random-secret")
    monkeypatch.setattr(settings, "dev_auth_email", "x@y.se")
    with pytest.raises(RuntimeError, match="DEV_AUTH_EMAIL"):
        _startup_checks()


def test_startup_ok_without_access(monkeypatch):
    from app.config import get_settings
    from app.main import _startup_checks

    settings = get_settings()
    monkeypatch.setattr(settings, "cf_access_aud", "")
    monkeypatch.setattr(settings, "secret_key", "dev-secret-change-me")
    _startup_checks()  # lokal utveckling — ska inte kasta


# ── CSRF: Origin-kontroll ─────────────────────────────────────


async def test_write_from_foreign_origin_rejected(client, make_token, known_user):
    resp = await client.put(
        "/api/nutrition-targets",
        headers={**auth(make_token), "Origin": "https://evil.example.com"},
        json={"kcal": 2000, "protein_g": 150, "carbs_g": 200, "fat_g": 70},
    )
    assert resp.status_code == 403


async def test_write_from_own_origin_allowed(client, make_token, known_user):
    # Testklienten anropar http://test → Host: test — samma origin är ok
    resp = await client.put(
        "/api/nutrition-targets",
        headers={**auth(make_token), "Origin": "http://test"},
        json={"kcal": 2000, "protein_g": 150, "carbs_g": 200, "fat_g": 70},
    )
    assert resp.status_code == 200


async def test_write_without_origin_allowed(client, make_token, known_user):
    # Icke-webbläsarklienter (curl, appar) skickar ingen Origin-header
    resp = await client.put(
        "/api/nutrition-targets",
        headers=auth(make_token),
        json={"kcal": 2000, "protein_g": 150, "carbs_g": 200, "fat_g": 70},
    )
    assert resp.status_code == 200


async def test_get_from_foreign_origin_allowed(client, make_token, known_user):
    # Läsande anrop ändrar inget — spärras inte av origin-kontrollen
    resp = await client.get(
        "/api/me",
        headers={**auth(make_token), "Origin": "https://evil.example.com"},
    )
    assert resp.status_code == 200


# ── Rate limiting på webhooks ─────────────────────────────────


async def test_webhook_rate_limit(client):
    import app.main as main_module

    main_module._rate_buckets.clear()
    last = None
    for _ in range(main_module._RATE_LIMIT_PER_MINUTE + 1):
        last = await client.post("/api/webhooks/strava", json={})
    assert last.status_code == 429

    # Annan klient-IP har egen budget
    other = await client.post(
        "/api/webhooks/strava",
        json={},
        headers={"CF-Connecting-IP": "203.0.113.7"},
    )
    assert other.status_code != 429
    main_module._rate_buckets.clear()


# ── Bildvalidering via magiska bytes ──────────────────────────


def test_sniff_image_formats():
    assert sniff_image(b"\xff\xd8\xff\xe0" + b"\x00" * 16) == "image/jpeg"
    assert sniff_image(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16) == "image/png"
    assert (
        sniff_image(b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 16) == "image/webp"
    )
    assert (
        sniff_image(b"\x00\x00\x00\x18ftypheic" + b"\x00" * 16) == "image/heic"
    )
    assert sniff_image(b"<script>alert(1)</script>") is None
    assert sniff_image(b"GIF89a") is None
    assert sniff_image(b"") is None


async def test_photo_upload_rejects_fake_image(client, make_token, known_user):
    # Content-Type säger JPEG men innehållet är HTML → ska avvisas
    resp = await client.post(
        "/api/photos",
        headers=auth(make_token),
        files={
            "file": ("evil.jpg", io.BytesIO(b"<html>hej</html>"), "image/jpeg")
        },
        data={"pose": "front"},
    )
    assert resp.status_code == 400


async def test_photo_upload_stores_sniffed_type(
    client, make_token, known_user, tmp_path, monkeypatch
):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "data_dir", str(tmp_path))
    # Ljuger om typen (webp) men skickar PNG — den sniffade typen gäller
    resp = await client.post(
        "/api/photos",
        headers=auth(make_token),
        files={
            "file": (
                "bild.webp",
                io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32),
                "image/webp",
            )
        },
        data={"pose": "front"},
    )
    assert resp.status_code == 201
    photo_id = resp.json()["id"]

    file_resp = await client.get(
        f"/api/photos/{photo_id}/file", headers=auth(make_token)
    )
    assert file_resp.headers["content-type"] == "image/png"


async def test_meal_vision_rejects_fake_image(client, make_token, known_user):
    resp = await client.post(
        "/api/ai/meal-vision",
        headers=auth(make_token),
        files={"file": ("mat.jpg", io.BytesIO(b"inte en bild"), "image/jpeg")},
    )
    assert resp.status_code == 400


# ── Streckkodsvalidering ──────────────────────────────────────


@pytest.mark.parametrize(
    "barcode", ["abc", "12345", "1" * 15, "%2e%2e%2f", "12 34 56"]
)
async def test_invalid_barcode_rejected(client, make_token, known_user, barcode):
    resp = await client.get(
        f"/api/food/barcode/{barcode}", headers=auth(make_token)
    )
    # 400 = regexvalideringen; 307/404 = traversal-försök som routern
    # normaliserar bort innan de ens når endpointen
    assert resp.status_code in (400, 307, 404)
    if resp.status_code == 400:
        assert resp.json()["detail"] == "Ogiltig streckkod."
