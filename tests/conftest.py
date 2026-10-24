"""Shared fixtures: every test runs against an empty schema "food" in a throwaway database.

The database comes from TEST_DATABASE_URL (default: the local test container, see README);
tests are skipped when it is not reachable. Never point it at the real database - every test
drops the schema.
"""
import os

import psycopg
import pytest

import config
import db

TEST_URL = os.getenv("TEST_DATABASE_URL", "postgresql://postgres:test@127.0.0.1:55432/test")


@pytest.fixture(autouse=True)
def fresh_schema(monkeypatch):
    """Point the server at the test database and recreate the schema for the test."""
    try:
        with psycopg.connect(TEST_URL, connect_timeout=3):
            pass
    except psycopg.OperationalError:
        if os.getenv("TEST_REQUIRE_DB") == "1":
            pytest.fail(f"test database not reachable: {TEST_URL}")
        pytest.skip(f"test database not reachable: {TEST_URL}")
    monkeypatch.setattr(config, "DATABASE_URL", TEST_URL)
    db.conn().execute("drop schema if exists food cascade")
    db.init_schema()
    yield
    db.conn().close()


@pytest.fixture(name="add_item")
def fixture_add_item():
    """Insert an item: add_item(name, source='bls', kcal=..., protein=..., ...) → its food_id."""
    def add(name: str, source: str = "bls", ref: str | None = None, **values) -> int:
        item = {"source": source, "source_ref": ref or name.lower(), "name": name}
        for key, value in values.items():
            item[key if key.startswith("serving") or key.endswith("_serving")
                 else f"{key}_100g"] = value
        return db.upsert_item(item)["id"]
    return add
