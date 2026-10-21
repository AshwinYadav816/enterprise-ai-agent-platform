from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
from fastapi import FastAPI

from app.core.config import Settings, get_settings
from app.main import create_app

TEST_ORIGIN = "http://localhost:5173"


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


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    # raise_app_exceptions=False: let the 500 handler's response reach the test
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
