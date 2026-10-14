"""Recipe tools: home-cooked dishes saved with their ingredients."""
from typing import Annotated

from pydantic import BaseModel

import calc
import db
from tools._shared import AS_NUMBER, NUMBER_SCHEMA, FoodError, RecipeName, doc, food_tool


class Ingredient(BaseModel):
    """One ingredient of a recipe."""
    food_id: Annotated[int, AS_NUMBER, NUMBER_SCHEMA,
                       doc("food_id of the ingredient (from food_search).")]
    grams: Annotated[float, AS_NUMBER, NUMBER_SCHEMA,
                     doc("Amount in grams as it goes into the pot - raw weight for raw "
                         "ingredients (ml ≈ g for liquids).")]


def _recipe(name: str) -> dict:
    recipe = db.find_recipe(name)
    if not recipe:
        names = ", ".join(r["name"] for r in db.list_recipes()) or "none"
        raise FoodError(f"There is no recipe '{name}'. Saved recipes: {names}.")
    return recipe


def recipe_totals(name: str) -> dict:
    """A recipe with its ingredients, total values, values per portion and - if the total
    weight is known - per 100 g of the finished dish."""
    recipe = _recipe(name)
    totals: dict = {}
    lines = []
    for item in db.recipe_items(recipe["id"]):
        values = calc.for_grams(item, float(item["grams"]))
        calc.add(totals, values)
        lines.append({"food_id": item["id"], "name": item["name"], "grams": float(item["grams"]),
                      "source": calc.SOURCE_LABEL[item["source"]], "kcal": values["kcal"]})
    portions = float(recipe["portions"])
    out = {"name": recipe["name"], "portions": portions, "ingredients": lines, "total": totals,
           "per_portion": calc.scale(totals, 1 / portions), "notes": recipe["notes"]}
    if recipe["total_weight_g"]:
        out["total_weight_g"] = float(recipe["total_weight_g"])
        out["per_100g"] = calc.scale(totals, 100 / float(recipe["total_weight_g"]))
    return out


@food_tool
def recipe_save(
    name: Annotated[str, doc("Name of the dish, e.g. 'Chili con Carne'. An existing recipe "
                             "with exactly this name is replaced.")],
    ingredients: Annotated[list[Ingredient], doc("All ingredients, e.g. "
                                                 "[{'food_id': 812, 'grams': 500}, "
                                                 "{'food_id': 77, 'grams': 400}].")],
    portions: Annotated[float, doc("AS_NUMBER of portions the recipe makes.")] = 1,
    total_weight_g: Annotated[float | None, doc("Weight of the finished dish in grams, if "
                                                "known. Needed to log amounts in grams "
                                                "('450 g from the pot').")] = None,
    notes: Annotated[str | None, doc("Free notes, e.g. preparation.")] = None,
) -> dict:
    """Save a home-cooked dish as a recipe, or replace one with the same name. Every ingredient
    must have values per 100 g (pick another hit in food_search otherwise). Returns the recipe
    like recipe_get."""
    if not ingredients:
        raise FoodError("ingredients is empty.")
    pairs = []
    for ingredient in ingredients:
        item = db.get_item(ingredient.food_id)
        if not item:
            raise FoodError(f"There is no food with food_id {ingredient.food_id}.")
        if item.get("kcal_100g") is None:
            raise FoodError(f"'{item['name']}' has no values per 100 g: pick another hit of "
                            "food_search for it.")
        if ingredient.grams <= 0:
            raise FoodError(f"The amount of '{item['name']}' must be more than 0 g.")
        pairs.append((item["id"], ingredient.grams))
    if portions <= 0:
        raise FoodError("portions must be more than 0.")
    db.save_recipe(name.strip(), portions, total_weight_g, notes, pairs)
    return recipe_totals(name.strip())


@food_tool
def recipe_get(name: RecipeName) -> dict:
    """A recipe with its ingredients, total values, values per portion and (if the total weight
    is known) per 100 g of the finished dish. For the values of an eaten amount use
    food_nutrition with {'recipe': name, 'servings': ...} or {'recipe': name, 'grams': ...}."""
    return recipe_totals(name)


@food_tool
def recipe_list() -> list[dict]:
    """All saved recipes: name, number of portions, total weight (if known)."""
    return [{"name": r["name"], "portions": float(r["portions"]),
             "total_weight_g": float(r["total_weight_g"]) if r["total_weight_g"] else None}
            for r in db.list_recipes()]


@food_tool
def recipe_delete(name: RecipeName) -> dict:
    """Delete a recipe for good (there is no undo). The foods it used stay."""
    recipe = _recipe(name)
    db.delete_recipe(recipe["id"])
    return {"deleted": recipe["name"]}
