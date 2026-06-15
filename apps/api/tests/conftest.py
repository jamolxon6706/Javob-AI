"""
Shared fixtures for all tests.

Uses an in-memory SQLite database (via aiosqlite) to avoid needing a real
Postgres instance in CI.  The Vector column is patched out for SQLite.
"""
import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from javobai.db.base import Base
from javobai.db.session import get_db
from javobai.redis import get_redis


# ── SQLite engine (no pgvector) ────────────────────────────────────────────
# Patch Vector columns to plain Text so SQLite accepts the schema
from sqlalchemy import Text
import javobai.db.models.faq as faq_module

faq_module.FAQ.embedding.property.columns[0].type = Text()  # type: ignore[attr-defined]

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
_SessionLocal = async_sessionmaker(_engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables() -> AsyncGenerator[None, None]:
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with _SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest.fixture
def mock_redis() -> MagicMock:
    """In-memory dict-backed redis mock."""
    store: dict[str, Any] = {}

    mock = MagicMock()

    async def setex(key: str, ttl: int, value: str) -> None:
        store[key] = value

    async def get(key: str) -> bytes | None:
        v = store.get(key)
        return v.encode() if isinstance(v, str) else v

    async def delete(key: str) -> None:
        store.pop(key, None)

    mock.setex = setex
    mock.get = get
    mock.delete = delete
    mock.aclose = AsyncMock()
    return mock


@pytest_asyncio.fixture
async def client(db: AsyncSession, mock_redis: MagicMock) -> AsyncGenerator[AsyncClient, None]:
    from javobai.main import app

    app.dependency_overrides[get_db] = lambda: db  # type: ignore[arg-type]
    app.dependency_overrides[get_redis] = lambda: mock_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
