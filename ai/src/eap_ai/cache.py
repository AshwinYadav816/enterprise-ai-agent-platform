"""Embedding cache: Redis when REDIS_URL is set, else an in-process LRU.

Keys are sha256(model + text), so a changed model or text never hits a stale vector.
Document embeddings never expire (unchanged chunks are not re-embedded on re-ingest);
query embeddings expire after query_embedding_ttl. Cache failures are logged and treated
as misses: the cache can make requests cheaper, never break them.
"""

import hashlib
import logging
import time
from array import array
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Sequence
from typing import Literal, Protocol

from eap_ai import llm
from eap_ai.config import get_settings

log = logging.getLogger(__name__)

Kind = Literal["doc", "query"]
KEY_PREFIX = "eap:emb"


class VectorCache(Protocol):
    async def get_many(self, keys: Sequence[str]) -> list[list[float] | None]: ...
    async def set_many(self, items: dict[str, list[float]], ttl: int | None) -> None: ...
    async def close(self) -> None: ...


def pack(vector: Sequence[float]) -> bytes:
    return array("f", vector).tobytes()


def unpack(data: bytes) -> list[float]:
    return array("f", data).tolist()


class MemoryCache:
    """Bounded LRU with optional per-entry expiry. Vectors stored as float32 bytes."""

    def __init__(self, max_items: int, clock: Callable[[], float] = time.monotonic) -> None:
        self.max_items = max_items
        self._clock = clock
        self._data: OrderedDict[str, tuple[float | None, bytes]] = OrderedDict()

    async def get_many(self, keys: Sequence[str]) -> list[list[float] | None]:
        now = self._clock()
        out: list[list[float] | None] = []
        for key in keys:
            entry = self._data.get(key)
            if entry is None or (entry[0] is not None and entry[0] <= now):
                self._data.pop(key, None)
                out.append(None)
                continue
            self._data.move_to_end(key)
            out.append(unpack(entry[1]))
        return out

    async def set_many(self, items: dict[str, list[float]], ttl: int | None) -> None:
        expires = self._clock() + ttl if ttl else None
        for key, vector in items.items():
            self._data[key] = (expires, pack(vector))
            self._data.move_to_end(key)
        while len(self._data) > self.max_items:
            self._data.popitem(last=False)

    async def close(self) -> None:
        self._data.clear()


class RedisCache:
    def __init__(self, url: str) -> None:
        import redis.asyncio as redis  # optional at runtime: only needed with REDIS_URL

        self._redis = redis.Redis.from_url(url, socket_timeout=2, socket_connect_timeout=2)

    async def get_many(self, keys: Sequence[str]) -> list[list[float] | None]:
        if not keys:
            return []
        values = await self._redis.mget(list(keys))
        return [unpack(v) if v else None for v in values]

    async def set_many(self, items: dict[str, list[float]], ttl: int | None) -> None:
        if not items:
            return
        async with self._redis.pipeline(transaction=False) as pipe:
            for key, vector in items.items():
                pipe.set(key, pack(vector), ex=ttl)
            await pipe.execute()

    async def close(self) -> None:
        await self._redis.aclose()


_cache: VectorCache | None = None


def get_cache() -> VectorCache:
    global _cache
    if _cache is None:
        s = get_settings()
        _cache = RedisCache(s.redis_url) if s.redis_url else MemoryCache(s.cache_max_items)
    return _cache


async def reset_cache() -> None:
    """Close and forget the cache (tests, settings change)."""
    global _cache
    if _cache is not None:
        await _cache.close()
    _cache = None


def embedding_key(text: str, kind: Kind, model: str | None = None) -> str:
    model = model or get_settings().embedding_model
    digest = hashlib.sha256(f"{model}\x00{text}".encode()).hexdigest()
    return f"{KEY_PREFIX}:{kind}:{digest}"


async def _safe_get(keys: list[str]) -> list[list[float] | None]:
    try:
        return await get_cache().get_many(keys)
    except Exception as exc:
        log.warning("Embedding cache read failed (%s); treating as miss", exc)
        return [None] * len(keys)


async def _safe_set(items: dict[str, list[float]], ttl: int | None) -> None:
    try:
        await get_cache().set_many(items, ttl)
    except Exception as exc:
        log.warning("Embedding cache write failed (%s); continuing", exc)


async def cached_embed_documents(
    texts: Sequence[str],
    embed: Callable[[list[str]], Awaitable[list[list[float]]]],
) -> list[list[float]]:
    """Vectors for texts, calling `embed` only for texts not already cached."""
    keys = [embedding_key(t, "doc") for t in texts]
    cached = await _safe_get(keys)
    missing: dict[str, str] = {}  # key -> text, de-duplicated
    for key, text, vec in zip(keys, texts, cached, strict=True):
        if vec is None:
            missing.setdefault(key, text)
    fresh: dict[str, list[float]] = {}
    if missing:
        vectors = await embed(list(missing.values()))
        fresh = dict(zip(missing.keys(), vectors, strict=True))
        await _safe_set(fresh, ttl=None)
    log.info("Embeddings: %d from cache, %d computed", len(texts) - len(missing), len(missing))
    return [vec if vec is not None else fresh[key] for key, vec in zip(keys, cached, strict=True)]


async def cached_embed_query(text: str) -> list[float]:
    key = embedding_key(text, "query")
    (vec,) = await _safe_get([key])
    if vec is not None:
        return vec
    vec = await llm.get_embedder().aembed_query(text)
    await _safe_set({key: vec}, ttl=get_settings().query_embedding_ttl)
    return vec
