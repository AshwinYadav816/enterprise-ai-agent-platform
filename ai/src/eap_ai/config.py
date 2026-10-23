"""Settings loaded from environment / .env. All tunables live here."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

Tier = Literal["fast", "smart"]
Task = Literal[
    "router",
    "rewrite",
    "classify",
    "summary",
    "map",
    "judge",
    "answer",
    "chat",
    "synthesis",
    "report",
    "meeting",
    "email",
    "document",
]

# Every LLM call names its task; the task picks the default model tier.
TASK_TIERS: dict[Task, Tier] = {
    "router": "fast",  # plan which agents run
    "rewrite": "fast",  # follow-up -> standalone question
    "classify": "fast",  # email request type and tone
    "summary": "fast",  # conversation history summary
    "map": "fast",  # one part of a long document / transcript
    "judge": "fast",  # eval/run_eval.py groundedness score (not used by the app)
    "answer": "smart",  # grounded answer with citations
    "chat": "smart",  # small talk
    "synthesis": "smart",  # final reply after several steps
    "report": "smart",
    "meeting": "smart",
    "email": "smart",
    "document": "smart",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Mistral
    mistral_api_key: SecretStr
    fast_model: str = "ministral-8b-latest"
    smart_model: str = "ministral-14b-latest"
    embedding_model: str = "mistral-embed"
    fast_reasoning_effort: str = "none"
    embed_batch_size: int = 16
    max_upload_mb: int = 25  # ingest rejects larger files
    llm_timeout: int = 60
    llm_max_retries: int = 2  # retries after the first attempt (429 / 5xx / timeouts)
    llm_retry_backoff: float = 1.0  # seconds; doubles each retry
    # Per-task model override, e.g. TASK_MODELS='{"email": "open-mistral-nemo"}'. Tasks without
    # one use their tier's model (TASK_TIERS below).
    task_models: dict[Task, str] = Field(default_factory=dict)
    # Tried in order, with the same request, when a model is busy / rate-limited / failing.
    # Verified for streaming and structured output. No 3b for smart tasks on purpose: a weaker
    # model writing grounded answers risks invented content, and "busy" is better than that.
    # (open-mistral-nemo is not an option: Mistral now serves it with ministral-8b.)
    fast_fallback_models: list[str] = ["ministral-3b-latest"]
    smart_fallback_models: list[str] = ["ministral-8b-latest"]

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr | None = None

    # Cache (Redis if redis_url is set, else in-process LRU)
    redis_url: str | None = None
    cache_max_items: int = 5000  # in-process LRU size (~4 KB per 1024-dim vector)
    query_embedding_ttl: int = 3600  # seconds

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

    # Agents: inputs longer than this use map-reduce, split into parts of map_chunk_tokens
    long_input_tokens: int = 6000
    map_chunk_tokens: int = 3000


@lru_cache
def get_settings() -> Settings:
    return Settings()
