# mcp-food

[![CI](https://github.com/StefanOOEOrg/mcp-food/actions/workflows/ci.yml/badge.svg)](https://github.com/StefanOOEOrg/mcp-food/actions/workflows/ci.yml)

MCP server (stdio) with the **nutrition values** of foods and of your own recipes. It only
supplies numbers; the food diary itself is
[mcp-nutrition](https://github.com/StefanOOEOrg/mcp-nutrition), whose `meal_log` takes the
same field names as the `total` of `food_nutrition` (`kcal`, `protein_g`, `carbs_g`, `fat_g`,
`fiber_g`, `sugar_g`).

- [Requirements](#requirements)
- [Data sources](#data-sources)
- [Setup](#setup)
- [Project structure](#project-structure)
- [Development](#development)
- [Scope / Limitations](#scope--limitations)
- [Tool reference](#tool-reference)

## Requirements

- **Python 3.11 or newer** — the pinned dependencies require it; the CI runs 3.11 and 3.14.
- **Postgres 17** with the `food` schema (shared with mcp-nutrition; the `db/` folder of that repo
  ships the container).
- Internet access only for Open Food Facts lookups; own foods and BLS work offline.
- Nothing else: no account, no API key, no open port — an MCP server over stdio for a local client.

## Data sources

| `source` | What | Licence |
|---|---|---|
| `my` | Own foods: products eaten regularly, values from labels (`food_save`); first import from the MyFitnessPal history | - |
| `off` | [Open Food Facts](https://world.openfoodfacts.org), products sold in Austria: live name search and barcode lookup, every hit is cached in the database | ODbL |
| `bls` | [BLS 4.0](https://www.blsdb.de) of the Max Rubner-Institut: ~7,100 basic foods, German names; Austrian words (Faschiertes, Topfen, Paradeiser ...) are translated | CC BY 4.0 |

Recipes are home-cooked dishes made of these foods (raw weights), with the number of portions
and optionally the weight of the finished dish (to log "450 g from the pot").

## Setup

The database is the Postgres container of mcp-nutrition (`db/` there, schema `food` here).
The server creates its schema and the extensions `pg_trgm`/`unaccent` on start.

```bash
python3 -m venv venv && venv/bin/pip install -r requirements.txt
echo 'FOOD_DATABASE_URL=postgresql://nutrition:<password>@127.0.0.1:5433/nutrition' > .env
venv/bin/python scripts/import_bls.py BLS_4_0_Daten_2025_DE.xlsx   # once
```

| Variable | Meaning |
|---|---|
| `FOOD_DATABASE_URL` | libpq URL of the database |
| `OFF_USER_AGENT` | User-Agent for Open Food Facts (default `mcp-food/1.0 (self-hosted)`) |
| `OFF_TIMEOUT_SECONDS` | HTTP timeout for Open Food Facts (default 15) |
| `LOG_LEVEL` | default `INFO` |

Install it with its own venv and `.env` and add it to Hermes' `config.yaml`:

```yaml
mcp_servers:
  mcp-food:
    command: /path/to/mcp-food/.venv/bin/python
    args: [/path/to/mcp-food/src/main.py]
```

## Project structure

```
mcp-food/
├── src/
│   ├── calc.py              # nutrition maths (per 100 g, portions, recipe totals)
│   ├── config.py            # FOOD_DATABASE_URL / OFF_* / LOG_LEVEL from the environment
│   ├── db.py                # connection handling + schema init
│   ├── main.py              # entry point (stdio)
│   ├── mcp_server.py        # composition root: server + tools
│   ├── off.py               # Open Food Facts client (search, barcode) with caching
│   ├── schema.sql           # the `food` schema
│   ├── server_instance.py   # the shared MCP server instance
│   ├── terms.py             # term handling for search (German names, Austrian words)
│   └── tools/               # food_* and recipe_* tools + _shared helpers
├── tests/                   # run against a throwaway Postgres (TEST_DATABASE_URL)
├── scripts/                 # BLS import + tool_reference.py
├── .github/workflows/ci.yml # pytest against a Postgres service + pylint, on 3.11 and 3.14
├── .env.example             # copy to .env
├── .pylintrc
├── pytest.ini
├── requirements.txt / requirements-dev.txt
├── LICENSE
└── README.md
```

## Development

```bash
venv/bin/pip install -r requirements-dev.txt
sudo docker run -d --rm --name pg-test -e POSTGRES_PASSWORD=test -e POSTGRES_DB=test \
    -p 127.0.0.1:55432:5432 --tmpfs /var/lib/postgresql/data postgres:17.11
venv/bin/python -m pytest          # TEST_DATABASE_URL overrides the test database
venv/bin/pylint src tests scripts  # must stay at 10/10
venv/bin/python scripts/tool_reference.py   # regenerate the tool reference below
```

Every test drops and recreates the schema - never point `TEST_DATABASE_URL` at the real
database.

## Scope / Limitations

- A single-user tool, not a service: it runs locally over stdio — no port of its own, no
  authentication, no multi-user support.
- It needs the Postgres container; without it every tool fails with a readable error, and the tests
  skip locally (in CI they fail instead, via `TEST_REQUIRE_DB=1`).
- Its data sources are uneven: own foods are only as good as their labels, Open Food Facts is
  community data (and offline when the API is not reachable), BLS 4.0 only covers basic foods.
- German food names are expected for BLS lookups; Austrian terms are translated, everything else is
  matched literally.
- Recipes use raw weights of the ingredients — cooked weights have to be weighed separately.

## Tool reference

<!-- tool-reference:start -->

### Food

#### `food_search`

Search foods by name. Returns the hits per source, each with food_id, name, brand, values per 100 g and - if known - per serving. Pick the hit that matches the state of the food (raw/cooked, fat level) and pass its food_id to food_nutrition.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `query` | text | yes | Name of the food or product, e.g. 'Skyr', 'Spar Vital Skyr', 'Haferflocken', 'chicken breast, raw'. Brand words narrow the search; every word must appear in the name or brand. |
| `source` | `auto` / `my` / `off` / `bls` | no (default `'auto'`) | Where to search: 'auto' = all three (own foods, Open Food Facts Austria, BLS); 'my' = own foods only; 'off' = packaged products; 'bls' = basic ingredients (German names, add 'roh' for raw). |
| `limit` | number | no (default `8`) | Maximum number of hits per source. |

#### `food_barcode_lookup`

Find a packaged product by its barcode: first among the own foods and cached products, then in Open Food Facts. Returns the product like food_search does (with food_id), or found=false if nobody knows the barcode.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `barcode` | text | yes | EAN/UPC barcode digits (8, 12, 13 or 14 digits), e.g. '9100000039954'. Spaces and dashes are ignored. |

#### `food_nutrition`

Nutrition values of a meal: every component with its amount, and the total. Each item is a food (food_id) or a saved recipe (recipe), with grams or servings. The keys of `total` (kcal, protein_g, carbs_g, fat_g, fiber_g, sugar_g, ...) are the fields of meal_log in mcp-nutrition: pass them on unchanged.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `items` | list | yes | The components of the meal, e.g. [{'food_id': 812, 'grams': 150}, {'food_id': 77, 'servings': 2}, {'recipe': 'Chili', 'grams': 450}]. |

#### `food_save`

Save an own food from its label (values per 100 g), or update it: the same barcode, or the same brand + name without barcode, overwrites the earlier values. Returns the food with its food_id; food_search(source='my') finds it from now on.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `name` | text | yes | Product name, e.g. 'High Protein Milchreis'. |
| `kcal_100g` | number | yes | Energy in kcal per 100 g (label: 'Energie ... kcal'). |
| `protein_100g` | number | yes | Protein in g per 100 g. |
| `carbs_100g` | number | yes | Carbohydrates in g per 100 g ('Kohlenhydrate'). |
| `fat_100g` | number | yes | Fat in g per 100 g. |
| `fiber_100g` | number | no (default `none`) | Fibre in g per 100 g ('Ballaststoffe'). |
| `sugar_100g` | number | no (default `none`) | Sugar in g per 100 g ('davon Zucker'). |
| `salt_100g` | number | no (default `none`) | Salt in g per 100 g. |
| `brand` | text | no (default `none`) | Brand, e.g. 'Dr. Oetker'. |
| `serving_g` | number | no (default `none`) | Grams of one serving, e.g. 200 (lets food_nutrition work with servings). |
| `serving_desc` | text | no (default `none`) | What one serving is, e.g. '1 Becher', '1 Scoop'. |
| `barcode` | text | no (default `none`) | Barcode digits, if known: food_barcode_lookup then finds the product. |

#### `food_list`

The own foods (source 'my'), most used first: the products eaten regularly.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `limit` | number | no (default `50`) | Maximum number of foods. |

### Recipe

#### `recipe_save`

Save a home-cooked dish as a recipe, or replace one with the same name. Every ingredient must have values per 100 g (pick another hit in food_search otherwise). Returns the recipe like recipe_get.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `name` | text | yes | Name of the dish, e.g. 'Chili con Carne'. An existing recipe with exactly this name is replaced. |
| `ingredients` | list | yes | All ingredients, e.g. [{'food_id': 812, 'grams': 500}, {'food_id': 77, 'grams': 400}]. |
| `portions` | number | no (default `1`) | AS_NUMBER of portions the recipe makes. |
| `total_weight_g` | number | no (default `none`) | Weight of the finished dish in grams, if known. Needed to log amounts in grams ('450 g from the pot'). |
| `notes` | text | no (default `none`) | Free notes, e.g. preparation. |

#### `recipe_get`

A recipe with its ingredients, total values, values per portion and (if the total weight is known) per 100 g of the finished dish. For the values of an eaten amount use food_nutrition with {'recipe': name, 'servings': ...} or {'recipe': name, 'grams': ...}.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `name` | text | yes | Name of a saved recipe as recipe_list shows it, e.g. 'Overnight Oats'. Case does not matter; a unique part of the name is enough. |

#### `recipe_list`

All saved recipes: name, number of portions, total weight (if known).

#### `recipe_delete`

Delete a recipe for good (there is no undo). The foods it used stay.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `name` | text | yes | Name of a saved recipe as recipe_list shows it, e.g. 'Overnight Oats'. Case does not matter; a unique part of the name is enough. |

<!-- tool-reference:end -->

## License

[MIT](LICENSE)
