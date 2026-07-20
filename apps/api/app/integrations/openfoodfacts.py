"""Open Food Facts — streckkodsuppslag och textsökning.

Uppslag cachas i food_items av anroparen, så OFF belastas bara första
gången en produkt skannas.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://world.openfoodfacts.org"
_HEADERS = {"User-Agent": "Bodify/0.1 (self-hosted; +https://github.com/Honken9/Bodify)"}


# OFF lagrar *_100g i gram (SI) — konvertera till våra enheter.
# (off-nyckel, vår nyckel, faktor från gram)
_MICRO_MAP = [
    ("salt_100g", "salt_g", 1),
    ("sugars_100g", "sugar_g", 1),
    ("saturated-fat_100g", "saturated_fat_g", 1),
    ("vitamin-a_100g", "vitamin_a_ug", 1e6),
    ("vitamin-c_100g", "vitamin_c_mg", 1e3),
    ("vitamin-d_100g", "vitamin_d_ug", 1e6),
    ("vitamin-b12_100g", "vitamin_b12_ug", 1e6),
    ("folates_100g", "folate_ug", 1e6),
    ("calcium_100g", "calcium_mg", 1e3),
    ("iron_100g", "iron_mg", 1e3),
    ("magnesium_100g", "magnesium_mg", 1e3),
    ("potassium_100g", "potassium_mg", 1e3),
    ("zinc_100g", "zinc_mg", 1e3),
]


def _normalize(product: dict) -> dict | None:
    nutriments = product.get("nutriments") or {}
    # Svenska produkter saknar ofta product_name men har namnet i andra
    # fält — prova hela kedjan innan produkten döms ut som namnlös.
    name = (
        product.get("product_name_sv")
        or product.get("product_name")
        or product.get("generic_name_sv")
        or product.get("generic_name")
        or product.get("abbreviated_product_name")
        or (product.get("brands") or "").split(",")[0].strip()
    )
    if not name:
        return None

    def _num(key: str) -> float:
        try:
            return round(float(nutriments.get(key) or 0), 1)
        except (TypeError, ValueError):
            return 0.0

    kcal = _num("energy-kcal_100g")
    if kcal == 0.0:
        kj = _num("energy_100g")  # vissa produkter har bara kJ
        kcal = round(kj / 4.184, 1) if kj else 0.0

    per_100g = {
        "kcal": kcal,
        "protein_g": _num("proteins_100g"),
        "carbs_g": _num("carbohydrates_100g"),
        "fat_g": _num("fat_100g"),
        "fiber_g": _num("fiber_100g"),
    }

    # Mikronäringsämnen tas bara med när källdata finns — aldrig nollor
    # som skulle kunna misstas för uppmätt frånvaro.
    for off_key, our_key, factor in _MICRO_MAP:
        raw = nutriments.get(off_key)
        if raw in (None, ""):
            continue
        try:
            value = float(raw) * factor
        except (TypeError, ValueError):
            continue
        if value > 0:
            per_100g[our_key] = round(value, 2)

    # Portionsvikt ("1 kex = 12 g") — OFF:s serving_quantity är i gram
    serving_g = None
    try:
        quantity = float(product.get("serving_quantity") or 0)
        if 1 <= quantity <= 2000:
            serving_g = round(quantity, 1)
    except (TypeError, ValueError):
        pass

    # Drycker mäts i ml — känns igen på förpacknings-/portionstexten
    import re as _re

    qty_text = (
        f"{product.get('quantity') or ''} {product.get('serving_size') or ''}"
    ).lower()
    unit = "ml" if _re.search(r"\d\s*(ml|cl|l)\b", qty_text) else "g"

    return {
        "barcode": product.get("code"),
        "name": name[:200],
        "brand": (product.get("brands") or "").split(",")[0].strip()[:120] or None,
        "per_100g": per_100g,
        "serving_g": serving_g,
        "unit": unit,
    }


class OFFUnavailable(Exception):
    """Open Food Facts svarar inte — skilj från 'produkten finns inte'."""


async def fetch_product(barcode: str) -> dict | None:
    """Slå upp en produkt på streckkod. Returnerar normaliserad dict,
    None om produkten inte finns, eller OFFUnavailable vid driftfel."""
    try:
        async with httpx.AsyncClient(timeout=8, headers=_HEADERS) as client:
            resp = await client.get(f"{BASE_URL}/api/v2/product/{barcode}.json")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("OFF-uppslag %s misslyckades: %s", barcode, exc)
        raise OFFUnavailable() from exc
    if data.get("status") != 1:
        logger.info("OFF: streckkod %s finns inte i databasen.", barcode)
        return None
    return _normalize(data["product"])


async def search_products(query: str, limit: int = 10) -> list[dict]:
    """Textsökning mot OFF. Returnerar lista av normaliserade produkter."""
    params = {
        "search_terms": query,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": limit,
        "fields": "code,product_name,product_name_sv,brands,nutriments",
    }
    try:
        async with httpx.AsyncClient(timeout=8, headers=_HEADERS) as client:
            resp = await client.get(f"{BASE_URL}/cgi/search.pl", params=params)
        resp.raise_for_status()
        products = resp.json().get("products", [])
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("OFF-sökning misslyckades: %s", exc)
        return []
    normalized = [_normalize(p) for p in products]
    return [p for p in normalized if p is not None]
