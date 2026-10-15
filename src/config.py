"""Central configuration for the mcp-food project.

Environment variables are read once here so the rest of the codebase can rely
on validated, well-known settings instead of scattering os.getenv() calls
across modules.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# === LOGGING ===
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# === DATABASE ===
# libpq connection string of the Postgres database that holds the schema "food", e.g.
# postgresql://nutrition:<password>@127.0.0.1:5433/nutrition. Kept in the .env next to the
# release.
DATABASE_URL = os.getenv("FOOD_DATABASE_URL", "")

# === OPEN FOOD FACTS ===
# OFF asks every client to identify itself: "<app>/<version> (<contact>)".
OFF_USER_AGENT = os.getenv("OFF_USER_AGENT", "mcp-food/1.0 (self-hosted)")
OFF_TIMEOUT_SECONDS = float(os.getenv("OFF_TIMEOUT_SECONDS", "15"))
