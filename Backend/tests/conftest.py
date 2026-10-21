import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
from alembic.config import Config
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from alembic import command
from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.ratelimit import RateLimiter, get_rate_limiter
from app.main import create_app

TEST_ORIGIN = "http://localhost:5173"
BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _test_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Isolate tests from the developer's real .env (secrets, AI_MODE=real, ...)."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("JWT_SECRET", "test-secret-not-for-production-use-0123456789")
    monkeypatch.setenv("AI_MODE", "fake")
    monkeypatch.setenv("CORS_ORIGINS", f'["{TEST_ORIGIN}"]')
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# --- database -----------------------------------------------------------------------------


def _test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL") or Settings.model_fields["test_database_url"].default
    if not url.rsplit("/", 1)[-1].endswith("_test"):  # never wipe a real database
        raise RuntimeError(f"Refusing to run tests against a non-test database: {url}")
    return url


def _migrate(url: str) -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
async def db_engine() -> AsyncIterator[AsyncEngine]:
    """Fresh schema once per test session: drop everything, then `alembic upgrade head`."""
    url = _test_database_url()
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    # env.py calls asyncio.run(); run it in a thread so it gets its own event loop.
    await asyncio.to_thread(_migrate, url)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Session inside an outer transaction that is always rolled back.

    Code under test may commit freely: with create_savepoint, commits only release savepoints.
    """
    async with db_engine.connect() as conn:
        outer = await conn.begin()
        session = AsyncSession(
            bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            await session.close()
            await outer.rollback()


# --- redis -------------------------------------------------------------------------------------


class FakeRedis:
    """In-memory stand-in for the two Redis commands the rate limiter uses."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    async def incr(self, name: str) -> int:
        self.counts[name] = self.counts.get(name, 0) + 1
        return self.counts[name]

    async def expire(self, name: str, time: int) -> bool:
        self.ttls[name] = time
        return True


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


# --- app / client -------------------------------------------------------------------------------


@pytest.fixture
def app(request: pytest.FixtureRequest, fake_redis: FakeRedis) -> FastAPI:
    application = create_app()
    # Frozen clock: fixed windows must not roll over mid-test (that made counts reset).
    application.dependency_overrides[get_rate_limiter] = lambda: RateLimiter(
        fake_redis, clock=lambda: 1_000_000.0
    )
    if "db" in request.fixturenames:  # only DB tests need Postgres
        session: AsyncSession = request.getfixturevalue("db")

        async def _test_db() -> AsyncIterator[AsyncSession]:
            yield session

        application.dependency_overrides[get_db] = _test_db
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    # raise_app_exceptions=False: let the 500 handler's response reach the test
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
