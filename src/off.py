"""Open Food Facts client: name search restricted to products sold in Austria, barcode lookup."""
import time

import httpx

import config

BASE = "https://world.openfoodfacts.org"
SEARCH_API = "https://search.openfoodfacts.org/search"
FIELDS = ("code,product_name,product_name_de,brands,serving_size,serving_quantity,nutriments,"
          "countries_tags")


def _client() -> httpx.Client:
    return httpx.Client(base_url=BASE, headers={"User-Agent": config.OFF_USER_AGENT},
                        timeout=config.OFF_TIMEOUT_SECONDS)


def _num(nutriments: dict, key: str) -> float | None:
    value = nutriments.get(key)
    try:
        return round(float(value), 2) if value is not None else None
    except (TypeError, ValueError):
        return None


def _first_brand(brands) -> str | None:
    if isinstance(brands, list):
        brands = ",".join(brands)
    return (brands or "").split(",")[0].strip() or None


def to_item(product: dict) -> dict | None:
    """Map an OFF product to a food.items row; None when it has no energy value."""
    nut = product.get("nutriments") or {}
    kcal = _num(nut, "energy-kcal_100g")
    if kcal is None and _num(nut, "energy_100g") is not None:
        kcal = round(_num(nut, "energy_100g") / 4.184, 1)
    if kcal is None:
        return None
    name = (product.get("product_name_de") or product.get("product_name") or "").strip()
    return {
        "source": "off",
        "source_ref": product["code"],
        "name": name or f"Produkt {product['code']}",
        "brand": _first_brand(product.get("brands")),
        "kcal_100g": kcal,
        "protein_100g": _num(nut, "proteins_100g"),
        "carbs_100g": _num(nut, "carbohydrates_100g"),
        "fat_100g": _num(nut, "fat_100g"),
        "fiber_100g": _num(nut, "fiber_100g"),
        "sugar_100g": _num(nut, "sugars_100g"),
        "satfat_100g": _num(nut, "saturated-fat_100g"),
        "salt_100g": _num(nut, "salt_100g"),
        "alcohol_100g": _num(nut, "alcohol_100g"),
        "serving_g": _num(product, "serving_quantity"),
        "serving_desc": product.get("serving_size"),
    }


def _search_classic(c: httpx.Client, query: str, limit: int) -> list[dict]:
    """Legacy full-text search (all words required, good ranking) — often rate limited (503)."""
    params = {
        "search_terms": query, "search_simple": 1, "json": 1, "page_size": limit,
        "tagtype_0": "countries", "tag_contains_0": "contains", "tag_0": "austria",
        "fields": FIELDS,
    }
    for delay in (0, 1, 2):
        time.sleep(delay)
        resp = c.get("/cgi/search.pl", params=params)
        if resp.status_code not in (429, 502, 503, 504):
            resp.raise_for_status()
            return resp.json().get("products", [])
    resp.raise_for_status()
    return []


def _search_new(c: httpx.Client, query: str, limit: int) -> list[dict]:
    """search-a-licious fallback: ORs the terms, so keep only hits containing every word."""
    params = {"q": f'{query} countries_tags:"en:austria"', "page_size": 50, "fields": FIELDS}
    resp = c.get(SEARCH_API, params=params)
    resp.raise_for_status()
    words = query.lower().split()

    def text(p: dict) -> str:
        brands = p.get("brands")
        brands = " ".join(brands) if isinstance(brands, list) else brands or ""
        return f"{p.get('product_name') or ''} {p.get('product_name_de') or ''} {brands}".lower()

    return [p for p in resp.json().get("hits", []) if all(w in text(p) for w in words)][:limit]


def search_austria(query: str, limit: int = 8) -> list[dict]:
    """Products sold in Austria whose name or brand contains every word of the query."""
    with _client() as client:
        try:
            products = _search_classic(client, query, limit)
        except httpx.HTTPError:
            products = _search_new(client, query, limit)
    return [i for i in (to_item(p) for p in products) if i]


def by_barcode(ean: str) -> dict | None:
    """The product with this barcode as an item row, or None when OFF does not know it."""
    with _client() as client:
        resp = client.get(f"/api/v2/product/{ean}.json", params={"fields": FIELDS})
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    body = resp.json()
    return to_item(body["product"]) if body.get("status") == 1 else None
