"""
Shared fixtures for worker tests.

Unit tests use mocks and don't need a DB.
Integration tests (marked with @pytest.mark.integration) require a real
PostgreSQL instance with pgvector; they are skipped automatically when
DATABASE_URL is not a Postgres URL.
"""
import os

import pytest

_DB_URL = os.getenv("DATABASE_URL", "")
# Integration tests run only when a real Postgres is available
POSTGRES_AVAILABLE = "postgresql" in _DB_URL and "aiosqlite" not in _DB_URL


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integration: requires a real PostgreSQL with pgvector")
