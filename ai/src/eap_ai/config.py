"""Settings loaded from environment / .env. All tunables live here."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Mistral
    mistral_api_key: SecretStr
    fast_model: str = "ministral-8b-latest"
    smart_model: str = "ministral-14b-latest"
    embedding_model: str = "mistral-embed"
    fast_reasoning_effort: str = "none"
    embed_batch_size: int = 16
    llm_timeout: int = 60
    llm_max_retries: int = 2

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr | None = None

    # Chunking
    chunk_size: int = 600
    chunk_overlap: int = 80

    # Retrieval
    top_k: int = 20
    final_k: int = 5
    # mistral-embed cosine scores are compressed: off-topic ~0.59-0.66, on-topic ~0.65-0.80
    score_threshold: float = 0.62
    mmr_lambda: float = 0.7
    max_context_tokens: int = 6000


@lru_cache
def get_settings() -> Settings:
    return Settings()
