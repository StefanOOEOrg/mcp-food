"""Postgres access for the schema "food": items (own foods, Open Food Facts, BLS) and recipes."""
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

import config

NUTRIENTS = ("kcal", "protein", "carbs", "fat", "fiber", "sugar", "satfat", "salt", "alcohol")
ITEM_COLUMNS = (
    "source", "source_ref", "name", "brand",
    *(f"{n}_100g" for n in NUTRIENTS),
    "serving_g", "serving_desc",
    "kcal_serving", "protein_serving", "carbs_serving", "fat_serving",
)
SCHEMA = Path(__file__).with_name("schema.sql")

_CONN: dict = {}


def conn() -> psycopg.Connection:
    """The process-wide connection (autocommit), reopened when it was closed."""
    current = _CONN.get("conn")
    if current is None or current.closed:
        current = _CONN["conn"] = psycopg.connect(config.DATABASE_URL, row_factory=dict_row,
                                                  autocommit=True)
    return current


def init_schema() -> None:
    """Create the extensions, the schema and its tables if they do not exist yet."""
    conn().execute(SCHEMA.read_text(encoding="utf-8"))


def upsert_item(item: dict) -> dict:
    """Insert or update an item by (source, source_ref); returns the stored row."""
    cols = [c for c in ITEM_COLUMNS if c in item]
    placeholders = ", ".join(f"%({c})s" for c in cols)
    updates = ", ".join(f"{c} = excluded.{c}" for c in cols if c not in ("source", "source_ref"))
    sql = (
        f"insert into food.items ({', '.join(cols)}) values ({placeholders}) "
        f"on conflict (source, source_ref) do update set {updates}, updated_at = now() "
        "returning *"
    )
    return conn().execute(sql, item).fetchone()


def _stem(word: str) -> str:
    """Tolerate German plural/singular (Tomaten/Tomate, Kartoffeln/Kartoffel)."""
    return word[:-1] if len(word) > 5 and word.endswith("n") else word


def search_items(query: str, sources: tuple[str, ...], limit: int) -> list[dict]:
    """Name search: every word must appear (also across spaces, "Haferflocken" finds
    "Hafer Flocken").

    Ranking: often used first, then trigram similarity of the space-free name to the query
    (favours short, basic names over composite dishes), then shorter names.
    """
    words = [_stem(w) for w in query.lower().split() if w]
    if not words:
        return []
    text = "unaccent(lower(name || ' ' || coalesce(brand, '')))"
    word_filter = " and ".join(
        f"({text} like unaccent(%s) or replace({text}, ' ', '') like unaccent(%s))" for _ in words)
    sql = (
        "select * from food.items "
        f"where source = any(%s) and {word_filter} "
        "order by uses desc, "
        "similarity(replace(unaccent(lower(name)), ' ', ''), unaccent(%s)) desc, "
        "length(name) limit %s"
    )
    params: list = [list(sources)]
    for word in words:
        params += [f"%{word}%", f"%{word}%"]
    params += ["".join(query.lower().split()), limit]
    return conn().execute(sql, params).fetchall()


def get_item(item_id: int) -> dict | None:
    """The item with this id, or None."""
    return conn().execute("select * from food.items where id = %s", (item_id,)).fetchone()


def get_item_by_ref(source: str, source_ref: str) -> dict | None:
    """The item with this source and source reference (e.g. an OFF barcode), or None."""
    return conn().execute("select * from food.items where source = %s and source_ref = %s",
                          (source, source_ref)).fetchone()


def own_items(limit: int) -> list[dict]:
    """The own foods, most used first."""
    return conn().execute("select * from food.items where source = 'my' "
                          "order by uses desc, name limit %s", (limit,)).fetchall()


def count_use(item_id: int) -> None:
    """Count one more use of the item (search ranks often used items first)."""
    conn().execute("update food.items set uses = uses + 1 where id = %s", (item_id,))


def save_recipe(name: str, portions: float, total_weight_g: float | None, notes: str | None,
                items: list[tuple[int, float]]) -> int:
    """Create or replace a recipe (matched by exact name) with its ingredients; returns its id."""
    with conn().transaction():
        row = conn().execute(
            "insert into food.recipes (name, portions, total_weight_g, notes) "
            "values (%s, %s, %s, %s) "
            "on conflict (name) do update set portions = excluded.portions, "
            "total_weight_g = excluded.total_weight_g, notes = excluded.notes, "
            "updated_at = now() returning id",
            (name, portions, total_weight_g, notes),
        ).fetchone()
        conn().execute("delete from food.recipe_items where recipe_id = %s", (row["id"],))
        for item_id, grams in items:
            conn().execute(
                "insert into food.recipe_items (recipe_id, item_id, grams) values (%s, %s, %s) "
                "on conflict (recipe_id, item_id) "
                "do update set grams = food.recipe_items.grams + excluded.grams",
                (row["id"], item_id, grams),
            )
    return row["id"]


def find_recipe(name: str) -> dict | None:
    """The recipe with this name (case-insensitive); else the shortest name containing it."""
    return conn().execute(
        "select * from food.recipes where lower(name) = lower(%s) or lower(name) like lower(%s) "
        "order by lower(name) = lower(%s) desc, length(name) limit 1",
        (name, f"%{name}%", name),
    ).fetchone()


def recipe_items(recipe_id: int) -> list[dict]:
    """The ingredients of a recipe (item rows plus their grams), largest first."""
    return conn().execute(
        "select ri.grams, i.* from food.recipe_items ri join food.items i on i.id = ri.item_id "
        "where ri.recipe_id = %s order by ri.grams desc",
        (recipe_id,),
    ).fetchall()


def list_recipes() -> list[dict]:
    """All recipes by name."""
    return conn().execute("select name, portions, total_weight_g, updated_at from food.recipes "
                          "order by name").fetchall()


def delete_recipe(recipe_id: int) -> None:
    """Delete a recipe and its ingredient list."""
    conn().execute("delete from food.recipes where id = %s", (recipe_id,))
