"""Fixtures for the tool tests: a few basic ingredients and a recipe made of them."""
import pytest

from tools.recipe import Ingredient, recipe_save


@pytest.fixture(name="oats")
def fixture_oats(add_item) -> int:
    """Haferflocken, 370 kcal / 13 g protein per 100 g."""
    return add_item("Haferflocken", kcal=370, protein=13, carbs=59, fat=7, fiber=10)


@pytest.fixture(name="milk")
def fixture_milk(add_item) -> int:
    """Vollmilch, 64 kcal per 100 g."""
    return add_item("Vollmilch 3,5 %", kcal=64, protein=3.3, carbs=4.8, fat=3.5)


@pytest.fixture(name="porridge")
def fixture_porridge(oats, milk) -> str:
    """Recipe 'Porridge': 100 g oats + 300 g milk, 2 portions, 400 g finished."""
    recipe_save("Porridge",
                [Ingredient(food_id=oats, grams=100), Ingredient(food_id=milk, grams=300)],
                portions=2, total_weight_g=400)
    return "Porridge"
