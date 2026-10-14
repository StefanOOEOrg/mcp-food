"""Tests for the nutrition arithmetic and the OFF product mapping."""
import calc
import off


def test_for_grams_uses_meal_log_names():
    """Values come out as kcal / <nutrient>_g; missing nutrients are left out."""
    item = {"kcal_100g": 200, "protein_100g": 10, "fat_100g": None}
    assert calc.for_grams(item, 50) == {"kcal": 100, "protein_g": 5}


def test_per_serving_prefers_grams_then_stored_values():
    """serving_g wins over stored per-serving values; neither → None."""
    assert calc.per_serving({"serving_g": 30, "kcal_100g": 400})["kcal"] == 120
    assert calc.per_serving({"kcal_serving": 150, "protein_serving": 20}) == {"kcal": 150,
                                                                             "protein_g": 20}
    assert calc.per_serving({"kcal_100g": 100}) is None


def test_off_product_without_kcal_uses_kilojoule():
    """OFF products with energy in kJ only are converted; products without energy are dropped."""
    product = {"code": "1", "product_name": "Saft", "brands": "A, B",
               "nutriments": {"energy_100g": 418.4, "sugars_100g": "10"}}
    item = off.to_item(product)
    assert item["kcal_100g"] == 100 and item["brand"] == "A" and item["sugar_100g"] == 10
    assert off.to_item({"code": "2", "nutriments": {}}) is None
