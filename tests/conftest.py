"""Shared test fixtures for HK-PropTech AI.

Uses SQLite with StaticPool for fast, isolated unit tests that do not
require a running PostgreSQL instance. For integration tests that need
pgvector, use the Docker test_db container instead.

Integration tests (marked with @pytest.mark.integration) use the pg_session
fixture which connects to a real PostgreSQL instance via TEST_DATABASE_URL.
"""

import asyncio
import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import StaticPool, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db
from app.main import app

# In-memory SQLite for unit tests (no pgvector features)
TEST_DATABASE_URL = "sqlite+aiosqlite:///file::memory:?cache=shared"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

test_session_factory = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for all tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create SQLite-compatible tables before each test, drop after.

    Tables that use PostgreSQL-only types (JSONB, TSVECTOR, pgvector Vector)
    are detected automatically by probing each table individually.
    Integration tests that need those tables use the pg_session fixture.
    """
    created_tables = []
    # sorted_tables respects FK dependency order
    for table in Base.metadata.sorted_tables:
        try:
            async with test_engine.begin() as conn:
                await conn.run_sync(lambda c, t=table: t.create(c))
            created_tables.append(table)
        except Exception:
            pass  # Skip tables with PostgreSQL-only types (JSONB, TSVECTOR, Vector)

    yield

    # Drop in reverse FK order
    for table in reversed(created_tables):
        try:
            async with test_engine.begin() as conn:
                await conn.run_sync(lambda c, t=table: t.drop(c))
        except Exception:
            pass


async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with test_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = _override_get_db


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Integration test fixtures — require real PostgreSQL + pgvector
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def pg_session() -> AsyncGenerator[AsyncSession, None]:
    """Real PostgreSQL session for integration tests.

    Requires TEST_DATABASE_URL env var (e.g. postgresql+asyncpg://...).
    Relies on ``alembic upgrade head`` (run before tests in CI) to have
    created the schema.  Uses TRUNCATE for per-test isolation instead of
    create_all / drop_all so that PostgreSQL ENUM types created by Alembic
    are never re-created or dropped mid-test-run (which causes "type already
    exists" / "type does not exist" errors).

    Run with: pytest -m integration
    """
    db_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://propman:propman_secret@localhost:5432/propman_ai",
    )
    engine = create_async_engine(db_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Truncate test tables before each test for a clean slate.
    # CASCADE handles the child_chunks FK automatically.
    async with factory() as pre_session:
        await pre_session.execute(text("TRUNCATE child_chunks, parent_docs CASCADE"))
        await pre_session.commit()

    async with factory() as session:
        try:
            yield session
        finally:
            await session.rollback()

    await engine.dispose()
