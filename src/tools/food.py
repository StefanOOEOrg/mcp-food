"""Food tools: search, barcode, nutrition of amounts, own foods."""
import logging
import re
from typing import Annotated, Literal

import httpx
from pydantic import BaseModel

import calc
import db
import off
from terms import to_german
from tools._shared import FoodError, doc, food_tool
from tools.recipe import recipe_totals

log = logging.getLogger(__name__)


class Amount(BaseModel):
    """One component of a meal: a food or a recipe, with its amount."""
    food_id: Annotated[int | None, doc("food_id of a food (from food_search). Give either "
                                       "food_id or recipe.")] = None
    recipe: Annotated[str | None, doc("Name of a saved recipe (from recipe_list). Give either "
                                      "food_id or recipe.")] = None
    grams: Annotated[float | None, doc("Amount in grams (for drinks: ml ≈ g). For a recipe: "
                                       "grams of the finished dish.")] = None
    servings: Annotated[float | None, doc("Number of servings of the food, or of portions of "
                                          "the recipe, e.g. 1.5. Used when grams is not "
                                          "given; default 1.")] = None


def _item(food_id: int) -> dict:
    item = db.get_item(food_id)
    if not item:
        raise FoodError(f"There is no food with food_id {food_id}. "
                        "Take the food_id from food_search.")
    return item


def _food_amount(entry: Amount) -> dict:
    item = _item(entry.food_id)
    if entry.grams is not None:
        values, amount = calc.for_grams(item, entry.grams), f"{entry.grams:g} g"
        if values is None:
            raise FoodError(f"'{item['name']}' has values per serving only: give servings "
                            "instead of grams.")
    else:
        count = entry.servings or 1
        serving = calc.per_serving(item)
        if serving is None:
            raise FoodError(f"'{item['name']}' has no serving size: give grams instead of "
                            "servings.")
        values = calc.scale(serving, count)
        amount = f"{count:g} × {item.get('serving_desc') or 'serving'}"
    db.count_use(item["id"])
    return {"food_id": item["id"], "name": item["name"], "brand": item.get("brand"),
            "amount": amount, "source": calc.SOURCE_LABEL[item["source"]], **values}


def _recipe_amount(entry: Amount) -> dict:
    recipe = recipe_totals(entry.recipe)
    if entry.grams is not None:
        if "per_100g" not in recipe:
            raise FoodError(f"Recipe '{recipe['name']}' has no total weight, so grams do not "
                            "work: give servings (portions) instead, or save the recipe again "
                            "with total_weight_g.")
        values, amount = calc.scale(recipe["per_100g"], entry.grams / 100), f"{entry.grams:g} g"
    else:
        count = entry.servings or 1
        values, amount = calc.scale(recipe["per_portion"], count), f"{count:g} portion(s)"
    return {"recipe": recipe["name"], "amount": amount, "source": "recipe", **values}


@food_tool
def food_search(
    query: Annotated[str, doc("Name of the food or product, e.g. 'Skyr', 'Spar Vital Skyr', "
                              "'Haferflocken', 'Hähnchenbrust roh'. Brand words narrow the "
                              "search; every word must appear in the name or brand.")],
    source: Annotated[Literal["auto", "my", "off", "bls"],
                      doc("Where to search: 'auto' = all three (own foods, Open Food Facts "
                          "Austria, BLS); 'my' = own foods only; 'off' = packaged products; "
                          "'bls' = basic ingredients (German names, add 'roh' for raw).")]
    = "auto",
    limit: Annotated[int, doc("Maximum number of hits per source.")] = 8,
) -> dict:
    """Search foods by name. Returns the hits per source, each with food_id, name, brand,
    values per 100 g and - if known - per serving. Pick the hit that matches the state of the
    food (raw/cooked, fat level) and pass its food_id to food_nutrition."""
    sources = ("my", "off", "bls") if source == "auto" else (source,)
    results: dict = {}
    if "my" in sources:
        results["my"] = [calc.describe(i) for i in db.search_items(query, ("my",), limit)]
    if "off" in sources:
        try:
            found = [db.upsert_item(i) for i in off.search_austria(query, limit)]
        except httpx.HTTPError as exc:  # network trouble must not hide the cached hits
            log.warning("Open Food Facts search failed: %s", exc)
            found = db.search_items(query, ("off",), limit)
            results["off_error"] = "Open Food Facts is not reachable; showing cached products."
        results["off"] = [calc.describe(i) for i in found]
    if "bls" in sources:
        results["bls"] = [calc.describe(i)
                          for i in db.search_items(to_german(query), ("bls",), limit)]
    if not any(results.get(s) for s in sources):
        results["hint"] = ("No hits. Try fewer or simpler words, the German name with "
                           "source 'bls', or save the product from its label with food_save.")
    return results


@food_tool
def food_barcode_lookup(
    barcode: Annotated[str, doc("EAN/UPC barcode digits (8, 12, 13 or 14 digits), e.g. "
                                "'9100000039954'. Spaces and dashes are ignored.")],
) -> dict:
    """Find a packaged product by its barcode: first among the own foods and cached products,
    then in Open Food Facts. Returns the product like food_search does (with food_id), or
    found=false if nobody knows the barcode."""
    code = re.sub(r"\D", "", barcode)
    if len(code) not in (8, 12, 13, 14):
        raise FoodError(f"'{barcode}' is not a barcode: it needs 8, 12, 13 or 14 digits.")
    for source in ("my", "off"):
        item = db.get_item_by_ref(source, code)
        if item:
            return calc.describe(item)
    try:
        item = off.by_barcode(code)
    except httpx.HTTPError as exc:
        raise FoodError("Open Food Facts is not reachable right now; try again later or read "
                        "the values from the label (food_save).") from exc
    if not item:
        return {"found": False, "barcode": code,
                "hint": "Not in Open Food Facts. Read the nutrition table on the label and save "
                        "the product with food_save (with this barcode)."}
    return calc.describe(db.upsert_item(item))


@food_tool
def food_nutrition(
    items: Annotated[list[Amount], doc("The components of the meal, e.g. "
                                       "[{'food_id': 812, 'grams': 150}, "
                                       "{'food_id': 77, 'servings': 2}, "
                                       "{'recipe': 'Chili', 'grams': 450}].")],
) -> dict:
    """Nutrition values of a meal: every component with its amount, and the total. Each item is
    a food (food_id) or a saved recipe (recipe), with grams or servings. The keys of `total`
    (kcal, protein_g, carbs_g, fat_g, fiber_g, sugar_g, ...) are the fields of meal_log in
    mcp-nutrition: pass them on unchanged."""
    if not items:
        raise FoodError("items is empty: give at least one food or recipe with its amount.")
    parts, total = [], {}
    for entry in items:
        if (entry.food_id is None) == (entry.recipe is None):
            raise FoodError("Every item needs exactly one of food_id or recipe.")
        part = _food_amount(entry) if entry.food_id is not None else _recipe_amount(entry)
        calc.add(total, {k: v for k, v in part.items() if k == "kcal" or k.endswith("_g")})
        parts.append(part)
    return {"items": parts, "total": total}


@food_tool
def food_save(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    name: Annotated[str, doc("Product name, e.g. 'High Protein Milchreis'.")],
    kcal_100g: Annotated[float, doc("Energy in kcal per 100 g (label: 'Energie ... kcal').")],
    protein_100g: Annotated[float, doc("Protein in g per 100 g.")],
    carbs_100g: Annotated[float, doc("Carbohydrates in g per 100 g ('Kohlenhydrate').")],
    fat_100g: Annotated[float, doc("Fat in g per 100 g.")],
    fiber_100g: Annotated[float | None, doc("Fibre in g per 100 g ('Ballaststoffe').")] = None,
    sugar_100g: Annotated[float | None, doc("Sugar in g per 100 g ('davon Zucker').")] = None,
    salt_100g: Annotated[float | None, doc("Salt in g per 100 g.")] = None,
    brand: Annotated[str | None, doc("Brand, e.g. 'Dr. Oetker'.")] = None,
    serving_g: Annotated[float | None, doc("Grams of one serving, e.g. 200 (lets "
                                           "food_nutrition work with servings).")] = None,
    serving_desc: Annotated[str | None, doc("What one serving is, e.g. '1 Becher', "
                                            "'1 Scoop'.")] = None,
    barcode: Annotated[str | None, doc("Barcode digits, if known: food_barcode_lookup then "
                                       "finds the product.")] = None,
) -> dict:
    """Save an own food from its label (values per 100 g), or update it: the same barcode, or
    the same brand + name without barcode, overwrites the earlier values. Returns the food with
    its food_id; food_search(source='my') finds it from now on."""
    ref = (re.sub(r"\D", "", barcode) if barcode
           else re.sub(r"[^a-z0-9]+", "-", f"{brand or ''} {name}".lower()).strip("-"))
    if not ref:
        raise FoodError("The name is empty.")
    item = db.upsert_item({
        "source": "my", "source_ref": ref, "name": name.strip(), "brand": brand,
        "kcal_100g": kcal_100g, "protein_100g": protein_100g, "carbs_100g": carbs_100g,
        "fat_100g": fat_100g, "fiber_100g": fiber_100g, "sugar_100g": sugar_100g,
        "salt_100g": salt_100g, "serving_g": serving_g, "serving_desc": serving_desc,
    })
    return calc.describe(item)


@food_tool
def food_list(
    limit: Annotated[int, doc("Maximum number of foods.")] = 50,
) -> list[dict]:
    """The own foods (source 'my'), most used first: the products eaten regularly."""
    return [calc.describe(i) for i in db.own_items(limit)]
