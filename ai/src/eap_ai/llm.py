"""Single place that builds LLM / embedding clients. Mistral only."""

import asyncio
import logging
import random
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any, Literal

import httpx
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from tokenizers import Tokenizer, models, pre_tokenizers  # installed with langchain-mistralai

from eap_ai.config import get_settings

log = logging.getLogger(__name__)

Tier = Literal["fast", "smart"]

_sleep = asyncio.sleep  # patched in tests

_EMBED_PROBE = "embedding dimension probe"
_embedding_dim: int | None = None


def _supports_reasoning_effort() -> bool:
    # Installed ChatMistralAI has no `reasoning_effort` field (only a generic model_kwargs
    # passthrough), so this stays False until the library declares it.
    return "reasoning_effort" in ChatMistralAI.model_fields


def is_retryable(exc: BaseException) -> bool:
    """Rate limits, server errors and timeouts are worth retrying; other errors are not."""
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code == 429 or code >= 500
    return False


def _causes(exc: BaseException) -> list[BaseException]:
    """The exception and what it wraps (tenacity RetryError, __cause__, __context__)."""
    seen: list[BaseException] = []
    todo: list[BaseException | None] = [exc]
    while todo:
        e = todo.pop()
        if e is None or any(e is s for s in seen) or len(seen) > 10:
            continue
        seen.append(e)
        attempt = getattr(e, "last_attempt", None)  # tenacity.RetryError (not a direct dep)
        if attempt is not None and attempt.failed:
            todo.append(attempt.exception())
        todo += [e.__cause__, e.__context__]
    return seen


def is_rate_limited(exc: BaseException) -> bool:
    """Mistral said 429: rate limit, or no capacity for the model right now (code 3505)."""
    for e in _causes(exc):
        response = getattr(e, "response", None)
        if getattr(response, "status_code", None) == 429:
            return True
        msg = str(e).lower()
        if "429" in msg or "rate limit" in msg or "capacity" in msg:
            return True
    return False


def is_provider_unavailable(exc: BaseException) -> bool:
    """The AI provider is busy or down (429, 5xx, timeout): a retry later may work."""
    return is_rate_limited(exc) or any(is_retryable(e) for e in _causes(exc))


class RetryingChatMistralAI(ChatMistralAI):
    """ChatMistralAI that also retries 429 / 5xx / timeouts with exponential backoff.

    The base class only retries network errors. Streams are retried only if the failure
    happens before the first chunk, so users never see duplicated text.
    """

    status_retries: int = 2
    retry_backoff: float = 1.0

    def _delay(self, attempt: int) -> float:
        return self.retry_backoff * 2**attempt + random.uniform(0, self.retry_backoff / 2)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        stream = kwargs.get("stream")
        if stream if stream is not None else self.streaming:  # _astream retries itself
            return await super()._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)
        for attempt in range(self.status_retries + 1):
            try:
                return await super()._agenerate(
                    messages, stop=stop, run_manager=run_manager, **kwargs
                )
            except Exception as exc:
                if attempt == self.status_retries or not is_retryable(exc):
                    raise
                delay = self._delay(attempt)
                log.warning("%s: %s; retry %d in %.1fs", self.model, exc, attempt + 1, delay)
                await _sleep(delay)
        raise AssertionError("unreachable")

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        for attempt in range(self.status_retries + 1):
            started = False
            try:
                async for chunk in super()._astream(
                    messages, stop=stop, run_manager=run_manager, **kwargs
                ):
                    started = True
                    yield chunk
                return
            except Exception as exc:
                if started or attempt == self.status_retries or not is_retryable(exc):
                    raise
                delay = self._delay(attempt)
                log.warning("%s stream: %s; retry %d in %.1fs", self.model, exc, attempt + 1, delay)
                await _sleep(delay)


@lru_cache
def get_chat_model(tier: Tier, streaming: bool = False) -> BaseChatModel:
    s = get_settings()
    kwargs: dict[str, object] = {}
    if tier == "fast" and _supports_reasoning_effort():
        kwargs["reasoning_effort"] = s.fast_reasoning_effort
    return RetryingChatMistralAI(
        model=s.fast_model if tier == "fast" else s.smart_model,
        api_key=s.mistral_api_key,
        streaming=streaming,
        timeout=s.llm_timeout,  # per HTTP call
        max_retries=s.llm_max_retries,  # network errors (base class)
        status_retries=s.llm_max_retries,  # 429 / 5xx / timeouts (this class)
        retry_backoff=s.llm_retry_backoff,
        **kwargs,
    )


def _offline_tokenizer() -> Tokenizer:
    """Word-count tokenizer for MistralAIEmbeddings' internal batch sizing.

    Without one, the library downloads a tokenizer from HuggingFace on first use (~30 s on a
    cold start, every fresh container). Our pipeline already batches by embed_batch_size, so a
    whitespace word count is accurate enough.
    """
    tokenizer = Tokenizer(models.WordLevel(vocab={"[UNK]": 0}, unk_token="[UNK]"))
    tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
    return tokenizer


@lru_cache
def get_embedder() -> Embeddings:
    s = get_settings()
    return MistralAIEmbeddings(
        model=s.embedding_model,
        api_key=s.mistral_api_key,
        timeout=s.llm_timeout,  # per HTTP call
        max_retries=s.llm_max_retries + 1,  # the library counts attempts, not retries
        wait_time=max(1, round(2 * s.llm_retry_backoff)),  # fixed wait between attempts
        tokenizer=_offline_tokenizer(),
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
