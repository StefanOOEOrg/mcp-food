"""Tests for the recipe tools."""
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from tools.recipe import Ingredient, recipe_delete, recipe_get, recipe_list, recipe_save


def test_get_shows_totals_portions_and_per_100g(porridge):
    """Totals, per portion and per 100 g of the finished dish."""
    recipe = recipe_get(porridge.lower())
    assert recipe["total"]["kcal"] == 562
    assert recipe["per_portion"]["kcal"] == 281
    assert recipe["per_100g"]["kcal"] == 140.5
    assert [i["grams"] for i in recipe["ingredients"]] == [300, 100]


def test_part_of_the_name_is_enough_and_exact_name_wins(oats, porridge):
    """'porr' finds Porridge; an exact name beats a longer one containing it."""
    recipe_save("Porridge XXL", [Ingredient(food_id=oats, grams=200)])
    assert recipe_get("porr")["name"] == porridge
    assert recipe_get("Porridge XXL")["name"] == "Porridge XXL"


def test_save_replaces_and_merges_duplicate_ingredients(oats, porridge):
    """Saving under the same name replaces; the same food twice is summed."""
    recipe_save(porridge, [Ingredient(food_id=oats, grams=40), Ingredient(food_id=oats, grams=60)])
    recipe = recipe_get(porridge)
    assert recipe["ingredients"] == [{"food_id": oats, "name": "Haferflocken", "grams": 100,
                                      "source": "BLS 4.0, Max Rubner-Institut (CC BY 4.0)",
                                      "kcal": 370}]
    assert "per_100g" not in recipe and recipe["portions"] == 1


def test_save_refuses_bad_ingredients(oats, add_item):
    """Unknown foods, foods without 100 g values and empty amounts are refused."""
    per_serving_only = add_item("Shake", source="my", kcal_serving=200)
    with pytest.raises(ToolError, match="food_id 999"):
        recipe_save("X", [Ingredient(food_id=999, grams=10)])
    with pytest.raises(ToolError, match="no values per 100 g"):
        recipe_save("X", [Ingredient(food_id=per_serving_only, grams=10)])
    with pytest.raises(ToolError, match="more than 0 g"):
        recipe_save("X", [Ingredient(food_id=oats, grams=0)])
    with pytest.raises(ToolError, match="empty"):
        recipe_save("X", [])


def test_list_and_delete(porridge):
    """recipe_list shows the recipe; after recipe_delete it is gone and the error lists the rest."""
    assert recipe_list() == [{"name": porridge, "portions": 2, "total_weight_g": 400}]
    assert recipe_delete("porridge") == {"deleted": porridge}
    with pytest.raises(ToolError, match="Saved recipes: none"):
        recipe_get(porridge)
