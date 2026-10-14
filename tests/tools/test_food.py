"""Tests for the food tools (Open Food Facts is replaced by fakes)."""
import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError

import off
from tools.food import (Amount, food_barcode_lookup, food_list, food_nutrition, food_save,
                        food_search)


@pytest.fixture(name="no_off")
def fixture_no_off(monkeypatch):
    """Open Food Facts knows nothing."""
    monkeypatch.setattr(off, "search_austria", lambda query, limit: [])
    monkeypatch.setattr(off, "by_barcode", lambda code: None)


def _offline(*_args):
    raise httpx.ConnectError("offline")


@pytest.mark.usefixtures("no_off")
def test_search_translates_austrian_words_for_bls(add_item):
    """'Faschiertes' finds the BLS 'Hackfleisch'."""
    add_item("Hackfleisch Rind roh", kcal=250, protein=20, carbs=0, fat=19)
    result = food_search("Faschiertes", source="bls")
    assert [i["name"] for i in result["bls"]] == ["Hackfleisch Rind roh"]


@pytest.mark.usefixtures("no_off")
def test_search_auto_covers_all_sources_and_hints_when_empty():
    """Without any hit every source is listed (empty) and a hint says what to try."""
    result = food_search("Drachenfrucht")
    assert result["my"] == [] and result["off"] == [] and result["bls"] == []
    assert "food_save" in result["hint"]


def test_search_falls_back_to_cache_when_off_is_offline(add_item, monkeypatch):
    """A network error shows the cached OFF products and says so."""
    add_item("Skyr Natur", source="off", ref="9000000000001", kcal=63, protein=11, carbs=4, fat=0.2)
    monkeypatch.setattr(off, "search_austria", _offline)
    result = food_search("Skyr", source="off")
    assert result["off"][0]["barcode"] == "9000000000001"
    assert "off_error" in result


def test_nutrition_sums_foods_and_recipes(oats, milk, porridge):
    """Grams, servings and recipe amounts add up to one total with meal_log field names."""
    result = food_nutrition([Amount(food_id=oats, grams=50), Amount(food_id=milk, grams=200),
                             Amount(recipe=porridge, servings=1)])
    assert [i["amount"] for i in result["items"]] == ["50 g", "200 g", "1 portion(s)"]
    # 50 g oats = 185 kcal, 200 g milk = 128 kcal, 1 of 2 portions (370 + 192) = 281 kcal
    assert result["total"]["kcal"] == 594
    assert result["total"]["protein_g"] == pytest.approx(6.5 + 6.6 + 11.45, abs=0.1)
    assert "fiber_g" in result["total"]


def test_nutrition_recipe_by_grams_of_finished_dish(porridge):
    """200 g of the 400 g pot are half the recipe."""
    result = food_nutrition([Amount(recipe=porridge, grams=200)])
    assert result["total"]["kcal"] == 281


def test_nutrition_servings_need_a_serving_size(oats):
    """A food without serving size refuses servings with a clear message."""
    with pytest.raises(ToolError, match="give grams"):
        food_nutrition([Amount(food_id=oats, servings=2)])


def test_nutrition_rejects_unknown_id_and_ambiguous_items(oats):
    """Unknown food_id and items with both or neither of food_id/recipe are refused."""
    with pytest.raises(ToolError, match="food_id 999"):
        food_nutrition([Amount(food_id=999, grams=10)])
    with pytest.raises(ToolError, match="exactly one"):
        food_nutrition([Amount(food_id=oats, recipe="Porridge", grams=10)])
    with pytest.raises(ToolError, match="empty"):
        food_nutrition([])


@pytest.mark.usefixtures("no_off")
def test_save_then_find_by_search_and_barcode():
    """An own food is found by name (source my) and by its barcode; saving again updates it."""
    saved = food_save("High Protein Milchreis", 85, 7.5, 10.5, 1.5, brand="Dr. Oetker",
                      serving_g=200, serving_desc="1 Becher", barcode="4023600-15195")
    assert saved["serving"]["kcal"] == 170
    assert food_search("Milchreis", source="my")["my"][0]["food_id"] == saved["food_id"]
    assert food_barcode_lookup("402360015195")["food_id"] == saved["food_id"]
    again = food_save("High Protein Milchreis", 90, 7.5, 10.5, 1.5, barcode="402360015195")
    assert again["food_id"] == saved["food_id"] and again["per_100g"]["kcal"] == 90


@pytest.mark.usefixtures("no_off")
def test_servings_of_own_food():
    """servings use the serving size of the food."""
    saved = food_save("Riegel", 400, 12, 70, 14, serving_g=40, serving_desc="1 Stück")
    total = food_nutrition([Amount(food_id=saved["food_id"], servings=2)])["total"]
    assert total["kcal"] == 320


@pytest.mark.usefixtures("no_off")
def test_barcode_unknown_and_invalid():
    """Unknown barcodes say what to do; non-barcodes are refused."""
    assert food_barcode_lookup("9100000039954")["found"] is False
    with pytest.raises(ToolError, match="not a barcode"):
        food_barcode_lookup("123")


def test_barcode_from_off_is_cached(monkeypatch):
    """A product found in OFF is stored, the second lookup needs no network."""
    product = {"source": "off", "source_ref": "9100000039954", "name": "Joghurt", "kcal_100g": 60}
    monkeypatch.setattr(off, "by_barcode", lambda code: product)
    first = food_barcode_lookup("9100000039954")
    monkeypatch.setattr(off, "by_barcode", _offline)
    assert food_barcode_lookup("9100000039954")["food_id"] == first["food_id"]


@pytest.mark.usefixtures("no_off")
def test_list_shows_most_used_first():
    """food_list orders the own foods by use."""
    rarely = food_save("Selten", 100, 1, 1, 1)
    often = food_save("Oft", 100, 1, 1, 1)
    food_nutrition([Amount(food_id=often["food_id"], grams=10)])
    assert [f["name"] for f in food_list()] == ["Oft", "Selten"]
    assert rarely["source"] == "own food"


def test_numbers_as_text_are_accepted(oats):
    """Numbers inside list items may arrive as text ('70', '1,5'); the schema allows that."""
    assert Amount(food_id=f"{oats}", grams="70").grams == 70
    assert Amount(food_id=oats, servings="1,5").servings == 1.5
    total = food_nutrition([Amount(food_id=str(oats), grams="50")])["total"]
    assert total["kcal"] == 185
    schema = Amount.model_json_schema()["properties"]
    assert {"type": "string"} in schema["grams"]["anyOf"]
    assert schema["grams"]["description"].startswith("Amount in grams")
    with pytest.raises(ValueError, match="not a number"):
        Amount(food_id=oats, grams="viel")
