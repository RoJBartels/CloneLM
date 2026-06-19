"""Shared test fixtures. Forces the deterministic fake providers so the suite
runs with no API key and no ML model. DB-dependent tests use ``db_available``
and skip cleanly when Postgres isn't up."""
from __future__ import annotations

import os

# Must be set before app.config is first imported (settings are cached).
os.environ.setdefault("LLM_PROVIDER", "fake")
os.environ.setdefault("EMBEDDING_PROVIDER", "fake")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


def _db_up() -> bool:
    try:
        from sqlalchemy import text

        from app.infrastructure.persistence.db import get_engine

        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def db_available() -> None:
    if not _db_up():
        pytest.skip("Postgres not reachable — run `docker compose up -d` for DB tests")
