"""Nutrition arithmetic and the compact item view the tools return.

Values leave this module under the names mcp-nutrition's meal_log takes (kcal, protein_g,
carbs_g, fat_g, fiber_g, sugar_g, ...), so a result can be passed on without renaming.
"""
from db import NUTRIENTS

SOURCE_LABEL = {
    "my": "own food",
    "off": "Open Food Facts (ODbL)",
    "bls": "BLS 4.0, Max Rubner-Institut (CC BY 4.0)",
}
SERVING_NUTRIENTS = ("kcal", "protein", "carbs", "fat")


def key(nutrient: str) -> str:
    """Output name of a nutrient: 'kcal' stays, the others are grams ('protein' → 'protein_g')."""
    return nutrient if nutrient == "kcal" else f"{nutrient}_g"


def for_grams(item: dict, grams: float) -> dict | None:
    """Nutrients for `grams` of an item; None when the item has no per-100 g data."""
    if item.get("kcal_100g") is None:
        return None
    factor = grams / 100
    return {key(n): round(float(item[f"{n}_100g"]) * factor, 1)
            for n in NUTRIENTS if item.get(f"{n}_100g") is not None}


def per_serving(item: dict) -> dict | None:
    """Nutrients of one serving: from serving_g and the 100 g values, else the stored
    per-serving values (foods known only per serving); None when neither exists."""
    if item.get("serving_g"):
        return for_grams(item, float(item["serving_g"]))
    if item.get("kcal_serving") is not None:
        return {key(n): float(item[f"{n}_serving"]) for n in SERVING_NUTRIENTS
                if item.get(f"{n}_serving") is not None}
    return None


def add(totals: dict, part: dict) -> dict:
    """Add the values of part to totals (in place) and return totals."""
    for name, value in part.items():
        totals[name] = round(totals.get(name, 0) + value, 1)
    return totals


def scale(values: dict, factor: float) -> dict:
    """All values multiplied by factor."""
    return {name: round(value * factor, 1) for name, value in values.items()}


def describe(item: dict) -> dict:
    """Compact, model-friendly view of an item."""
    per_100g = {key(n): float(item[f"{n}_100g"]) for n in NUTRIENTS
                if item.get(f"{n}_100g") is not None}
    out = {
        "food_id": item["id"],
        "name": item["name"],
        "brand": item.get("brand"),
        "source": SOURCE_LABEL[item["source"]],
        "per_100g": per_100g or None,
    }
    serving = per_serving(item)
    if serving:
        grams = item.get("serving_g")
        out["serving"] = {"desc": item.get("serving_desc"),
                          "grams": float(grams) if grams else None, **serving}
    if item["source"] == "off":
        out["barcode"] = item["source_ref"]
    return out
