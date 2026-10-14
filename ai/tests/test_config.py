import pytest

from eap_ai.config import Settings, get_settings


def test_settings_defaults() -> None:
    s = Settings(_env_file=None)
    assert s.mistral_api_key.get_secret_value() == "test-key"
    assert s.fast_model == "ministral-8b-latest"
    assert s.smart_model == "ministral-14b-latest"
    assert s.embedding_model == "mistral-embed"
    assert s.fast_reasoning_effort == "none"
    assert (s.chunk_size, s.chunk_overlap) == (600, 80)
    assert (s.top_k, s.final_k) == (20, 5)
    assert s.score_threshold == 0.35
    assert s.max_context_tokens == 6000
    assert s.qdrant_api_key is None


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOP_K", "10")
    monkeypatch.setenv("SCORE_THRESHOLD", "0.5")
    s = Settings(_env_file=None)
    assert s.top_k == 10
    assert s.score_threshold == 0.5


def test_api_key_is_secret() -> None:
    assert "test-key" not in repr(get_settings())
