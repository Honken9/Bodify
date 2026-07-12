"""Open Food Facts — streckkodsuppslag och textsökning.

Uppslag cachas i food_items av anroparen, så OFF belastas bara första
gången en produkt skannas.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://world.openfoodfacts.org"
_HEADERS = {"User-Agent": "Bodify/0.1 (self-hosted; +https://github.com/Honken9/Bodify)"}


def _normalize(product: dict) -> dict | None:
    nutriments = product.get("nutriments") or {}
    name = product.get("product_name_sv") or product.get("product_name")
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

    return {
        "barcode": product.get("code"),
        "name": name[:200],
        "brand": (product.get("brands") or "").split(",")[0].strip()[:120] or None,
        "per_100g": {
            "kcal": kcal,
            "protein_g": _num("proteins_100g"),
            "carbs_g": _num("carbohydrates_100g"),
            "fat_g": _num("fat_100g"),
            "fiber_g": _num("fiber_100g"),
        },
    }


async def fetch_product(barcode: str) -> dict | None:
    """Slå upp en produkt på streckkod. Returnerar normaliserad dict eller None."""
    async with httpx.AsyncClient(timeout=8, headers=_HEADERS) as client:
        resp = await client.get(f"{BASE_URL}/api/v2/product/{barcode}.json")
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != 1:
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
