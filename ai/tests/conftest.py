from collections.abc import Iterator

import pytest

from eap_ai.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _test_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Isolate tests from the developer's real .env and API key."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
