import pytest

from app.auth import ACCESS_JWT_HEADER
from app.integrations import openfoodfacts

KVARG = {
    "barcode": "7310865004703",
    "name": "Kvarg vanilj",
    "brand": "Arla",
    "per_100g": {
        "kcal": 57.0,
        "protein_g": 10.0,
        "carbs_g": 4.0,
        "fat_g": 0.2,
        "fiber_g": 0.0,
    },
}


def auth(make_token, email="daniel@example.com"):
    return {ACCESS_JWT_HEADER: make_token(email=email)}


@pytest.fixture
def mock_off(monkeypatch):
    async def fake_fetch(barcode: str):
        return dict(KVARG) if barcode == KVARG["barcode"] else None

    async def fake_search(query: str, limit: int = 10):
        return [dict(KVARG)] if "kvarg" in query.lower() else []

    monkeypatch.setattr(openfoodfacts, "fetch_product", fake_fetch)
    monkeypatch.setattr(openfoodfacts, "search_products", fake_search)


async def test_barcode_lookup_caches(client, make_token, known_user, mock_off, monkeypatch):
    resp = await client.get(
        f"/api/food/barcode/{KVARG['barcode']}", headers=auth(make_token)
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Kvarg vanilj"
    assert resp.json()["source"] == "off"

    # Andra uppslaget ska träffa cachen — OFF får inte anropas igen
    async def boom(barcode):
        raise AssertionError("OFF anropades trots cache")

    monkeypatch.setattr(openfoodfacts, "fetch_product", boom)
    resp2 = await client.get(
        f"/api/food/barcode/{KVARG['barcode']}", headers=auth(make_token)
    )
    assert resp2.status_code == 200
    assert resp2.json()["id"] == resp.json()["id"]


async def test_barcode_unknown_404(client, make_token, known_user, mock_off):
    resp = await client.get("/api/food/barcode/000000", headers=auth(make_token))
    assert resp.status_code == 404


async def test_search_merges_off_results(client, make_token, known_user, mock_off):
    resp = await client.get("/api/food/search?q=kvarg", headers=auth(make_token))
    assert resp.status_code == 200
    names = [f["name"] for f in resp.json()]
    assert "Kvarg vanilj" in names


async def test_custom_food_is_private(
    client, make_token, known_user, other_user, mock_off
):
    resp = await client.post(
        "/api/food",
        headers=auth(make_token),
        json={
            "name": "Mammas köttbullar",
            "per_100g": {"kcal": 220, "protein_g": 15, "carbs_g": 8, "fat_g": 14},
        },
    )
    assert resp.status_code == 201

    mine = await client.get(
        "/api/food/search?q=köttbullar", headers=auth(make_token)
    )
    assert len(mine.json()) == 1

    theirs = await client.get(
        "/api/food/search?q=köttbullar",
        headers=auth(make_token, "anna@example.com"),
    )
    assert theirs.json() == []


async def test_meal_entry_macro_math(client, make_token, known_user, mock_off):
    food = (
        await client.get(
            f"/api/food/barcode/{KVARG['barcode']}", headers=auth(make_token)
        )
    ).json()

    resp = await client.post(
        "/api/meals",
        headers=auth(make_token),
        json={
            "eaten_on": "2026-07-12",
            "meal": "breakfast",
            "food_item_id": food["id"],
            "grams": 250,
        },
    )
    assert resp.status_code == 201
    entry = resp.json()
    # 250 g × 57 kcal/100 g = 142.5 kcal, 25 g protein
    assert entry["kcal"] == 142.5
    assert entry["protein_g"] == 25.0

    day = (
        await client.get("/api/meals?day=2026-07-12", headers=auth(make_token))
    ).json()
    assert day["totals"]["kcal"] == 142.5
    assert day["targets"]["kcal"] == 2500  # default skapas automatiskt


async def test_update_targets(client, make_token, known_user):
    resp = await client.put(
        "/api/nutrition-targets",
        headers=auth(make_token),
        json={"kcal": 2200, "protein_g": 180, "carbs_g": 200, "fat_g": 70},
    )
    assert resp.status_code == 200
    assert resp.json()["protein_g"] == 180

    day = (await client.get("/api/meals", headers=auth(make_token))).json()
    assert day["targets"]["kcal"] == 2200


async def test_template_from_meal_and_apply(
    client, make_token, known_user, mock_off
):
    food = (
        await client.get(
            f"/api/food/barcode/{KVARG['barcode']}", headers=auth(make_token)
        )
    ).json()
    await client.post(
        "/api/meals",
        headers=auth(make_token),
        json={
            "eaten_on": "2026-07-12",
            "meal": "breakfast",
            "food_item_id": food["id"],
            "grams": 250,
        },
    )

    template = (
        await client.post(
            "/api/meal-templates/from-meal",
            headers=auth(make_token),
            json={
                "name": "Standardfrukost",
                "eaten_on": "2026-07-12",
                "meal": "breakfast",
            },
        )
    ).json()
    assert template["items"] == [{"food_item_id": food["id"], "grams": 250.0}]

    applied = await client.post(
        f"/api/meal-templates/{template['id']}/apply",
        headers=auth(make_token),
        json={"eaten_on": "2026-07-13", "meal": "breakfast"},
    )
    assert applied.status_code == 200
    assert applied.json()[0]["kcal"] == 142.5

    day = (
        await client.get("/api/meals?day=2026-07-13", headers=auth(make_token))
    ).json()
    assert day["totals"]["protein_g"] == 25.0


async def test_summary_groups_by_day(client, make_token, known_user, mock_off):
    from datetime import date

    food = (
        await client.get(
            f"/api/food/barcode/{KVARG['barcode']}", headers=auth(make_token)
        )
    ).json()
    today = date.today().isoformat()
    for meal in ("breakfast", "lunch"):
        await client.post(
            "/api/meals",
            headers=auth(make_token),
            json={
                "eaten_on": today,
                "meal": meal,
                "food_item_id": food["id"],
                "grams": 100,
            },
        )

    resp = await client.get("/api/meals/summary?days=7", headers=auth(make_token))
    [row] = resp.json()
    assert row["day"] == today
    assert row["kcal"] == 114.0
    assert row["entry_count"] == 2


def test_off_normalize_extracts_micros():
    from app.integrations.openfoodfacts import _normalize

    product = {
        "code": "7310000000001",
        "product_name": "Mellanmjölk",
        "nutriments": {
            "energy-kcal_100g": 47,
            "proteins_100g": 3.5,
            "carbohydrates_100g": 4.9,
            "fat_100g": 1.5,
            "fiber_100g": 0,
            "salt_100g": 0.1,
            "sugars_100g": 4.9,
            "saturated-fat_100g": 1.0,
            "calcium_100g": 0.12,  # gram → 120 mg
            "vitamin-d_100g": 1e-6,  # gram → 1 µg
            "vitamin-c_100g": 0.012,  # gram → 12 mg
            "iron_100g": 0.0007,  # gram → 0.7 mg
        },
    }
    per = _normalize(product)["per_100g"]
    assert per["calcium_mg"] == 120
    assert per["vitamin_d_ug"] == 1
    assert per["vitamin_c_mg"] == 12
    assert per["iron_mg"] == 0.7
    assert per["salt_g"] == 0.1
    assert per["sugar_g"] == 4.9
    assert per["saturated_fat_g"] == 1.0
    # Zink saknades i källan → ska INTE finnas (ingen falsk nolla)
    assert "zinc_mg" not in per


async def test_day_micros_with_rdi_percent(
    client, make_token, known_user, db_session
):
    from app.models import FoodItem

    milk = FoodItem(
        name="Berikad mjölk",
        source="custom",
        created_by=known_user.id,
        per_100g={
            "kcal": 47,
            "protein_g": 3.5,
            "carbs_g": 4.9,
            "fat_g": 1.5,
            "calcium_mg": 120,
            "vitamin_d_ug": 1.0,
            "salt_g": 0.1,
        },
    )
    db_session.add(milk)
    await db_session.commit()

    await client.post(
        "/api/meals",
        headers=auth(make_token),
        json={
            "eaten_on": "2026-07-16",
            "meal": "breakfast",
            "food_item_id": str(milk.id),
            "grams": 500,
        },
    )
    day = (
        await client.get("/api/meals?day=2026-07-16", headers=auth(make_token))
    ).json()
    micros = {m["key"]: m for m in day["micros"]}

    # 500 g × 120 mg/100 g = 600 mg kalcium; RDI 950 → 63 %
    assert micros["calcium_mg"]["amount"] == 600.0
    assert micros["calcium_mg"]["percent"] == 63
    assert micros["calcium_mg"]["kind"] == "rdi"
    # 5 µg D-vitamin av 10 → 50 %
    assert micros["vitamin_d_ug"]["percent"] == 50
    # Salt är en maxgräns: 0.5 g av 6 → 8 %
    assert micros["salt_g"]["kind"] == "max"
    assert micros["salt_g"]["percent"] == 8
    # Järn saknar källdata → ska inte visas alls
    assert "iron_mg" not in micros


async def test_meal_isolation(
    client, make_token, known_user, other_user, mock_off
):
    food = (
        await client.get(
            f"/api/food/barcode/{KVARG['barcode']}", headers=auth(make_token)
        )
    ).json()
    entry = (
        await client.post(
            "/api/meals",
            headers=auth(make_token),
            json={
                "eaten_on": "2026-07-12",
                "meal": "lunch",
                "food_item_id": food["id"],
                "grams": 100,
            },
        )
    ).json()

    anna = auth(make_token, "anna@example.com")
    day = (await client.get("/api/meals?day=2026-07-12", headers=anna)).json()
    assert day["entries"] == []
    assert (
        await client.delete(f"/api/meals/{entry['id']}", headers=anna)
    ).status_code == 404
