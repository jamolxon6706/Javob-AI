"""
Shared fixtures for all tests.

env vars are set BEFORE javobai imports so pydantic-settings picks them up.
Uses in-memory SQLite (aiosqlite). Vector column patched to Text for SQLite.
"""
import os

from cryptography.fernet import Fernet

# ── Must happen before any javobai import ─────────────────────────────────
os.environ.setdefault("FERNET_KEY", Fernet.generate_key().decode())
os.environ.setdefault("JWT_SECRET", "test_jwt_secret_for_testing_only_64_chars_xxxx")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

# ── Imports ────────────────────────────────────────────────────────────────
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from javobai.db.base import Base
from javobai.db.session import get_db
from javobai.redis import get_redis

# Patch Vector → Text so SQLite doesn't reject the schema
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
    """Dict-backed Redis mock (SETNX / GET / DELETE / EXPIRE / SETEX)."""
    store: dict[str, Any] = {}
    mock = MagicMock()

    async def setex(key: str, ttl: int, value: str) -> None:
        store[key] = value

    async def setnx(key: str, value: str) -> int:
        if key in store:
            return 0
        store[key] = value
        return 1

    async def expire(key: str, ttl: int) -> None:
        pass

    async def get(key: str) -> bytes | None:
        v = store.get(key)
        return v.encode() if isinstance(v, str) else v

    async def delete(key: str) -> None:
        store.pop(key, None)

    mock.setex = setex
    mock.setnx = setnx
    mock.expire = expire
    mock.get = get
    mock.delete = delete
    mock.aclose = AsyncMock()
    return mock


@pytest.fixture
def mock_arq() -> AsyncMock:
    """ARQ pool mock — captures enqueue_job calls."""
    arq = AsyncMock()
    arq.enqueue_job = AsyncMock()
    arq.aclose = AsyncMock()
    return arq


@pytest_asyncio.fixture
async def client(
    db: AsyncSession, mock_redis: MagicMock, mock_arq: AsyncMock
) -> AsyncGenerator[AsyncClient, None]:
    from javobai.main import app

    app.dependency_overrides[get_db] = lambda: db  # type: ignore[arg-type]
    app.dependency_overrides[get_redis] = lambda: mock_redis
    app.state.arq = mock_arq  # inject ARQ pool without running lifespan

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
