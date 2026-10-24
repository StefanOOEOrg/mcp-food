# Changelog

## 0.1.0 — 2026-10-24

Initial release.

- **Food:** `food_search` (name search across own foods, Open Food Facts and BLS), `food_barcode_lookup`
  (Open Food Facts by barcode, cached), `food_nutrition` (values per 100 g and per portion, with the
  `total` in the field names mcp-nutrition expects), `food_save` (own foods from a label), `food_list`.
- **Recipes:** `recipe_save` (ingredients with raw weights, portions, optional finished weight),
  `recipe_get`, `recipe_list`, `recipe_delete` — the recipe total is built from its ingredients.
- Three data sources with different reliability: own foods (labels), Open Food Facts (community data,
  cached in the database), BLS 4.0 (basic foods, German names, Austrian terms translated).
- Postgres-backed (`food` schema, shared with mcp-nutrition); schema from `src/schema.sql`.
- Local MCP server over stdio; configuration via `.env` (`FOOD_DATABASE_URL`, `OFF_USER_AGENT`,
  `OFF_TIMEOUT_SECONDS`, `LOG_LEVEL`); `.env.example` ships the template.
- CI: pytest against a Postgres service plus pylint on Python 3.11 and 3.14 — the run fails when the
  database is unreachable instead of silently skipping.
