"""Single place that builds LLM / embedding clients. Mistral only."""

from functools import lru_cache
from typing import Literal

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings

from eap_ai.config import get_settings

Tier = Literal["fast", "smart"]

_EMBED_PROBE = "embedding dimension probe"
_embedding_dim: int | None = None


def _supports_reasoning_effort() -> bool:
    # Installed ChatMistralAI has no `reasoning_effort` field (only a generic model_kwargs
    # passthrough), so this stays False until the library declares it.
    return "reasoning_effort" in ChatMistralAI.model_fields


@lru_cache
def get_chat_model(tier: Tier, streaming: bool = False) -> BaseChatModel:
    s = get_settings()
    kwargs: dict[str, object] = {}
    if tier == "fast" and _supports_reasoning_effort():
        kwargs["reasoning_effort"] = s.fast_reasoning_effort
    return ChatMistralAI(
        model=s.fast_model if tier == "fast" else s.smart_model,
        api_key=s.mistral_api_key,
        streaming=streaming,
        max_retries=s.llm_max_retries,
        timeout=s.llm_timeout,
        **kwargs,
    )


@lru_cache
def get_embedder() -> Embeddings:
    s = get_settings()
    return MistralAIEmbeddings(
        model=s.embedding_model,
        api_key=s.mistral_api_key,
        max_retries=s.llm_max_retries,
        timeout=s.llm_timeout,
    )


async def embedding_dim() -> int:
    """Vector size of the configured embedder, computed once by embedding a probe string."""
    global _embedding_dim
    if _embedding_dim is None:
        _embedding_dim = len(await get_embedder().aembed_query(_EMBED_PROBE))
    return _embedding_dim


_CACHED_FACTORIES = (get_chat_model, get_embedder)  # survive monkeypatching in tests


def clear_caches() -> None:
    """Drop cached clients (used by tests and after settings change)."""
    global _embedding_dim
    _embedding_dim = None
    for factory in _CACHED_FACTORIES:
        factory.cache_clear()
