"""Ingestion: load -> chunk -> embed (batched, 429-aware) -> replace points in Qdrant."""

import asyncio
import logging

from eap_ai import llm
from eap_ai.cache import cached_embed_documents
from eap_ai.config import get_settings
from eap_ai.ingestion.chunker import chunk_pages
from eap_ai.ingestion.loaders import load_document
from eap_ai.schemas import DocMeta, IngestResult
from eap_ai.vectorstore import qdrant

log = logging.getLogger(__name__)

RATE_LIMIT_RETRIES = 5
BACKOFF_BASE_SECONDS = 2.0
BACKOFF_MAX_SECONDS = 60.0

_sleep = asyncio.sleep  # patched in tests


async def _embed_batch(texts: list[str]) -> list[list[float]]:
    embedder = llm.get_embedder()
    for attempt in range(RATE_LIMIT_RETRIES + 1):
        try:
            return await embedder.aembed_documents(texts)
        except Exception as exc:
            if not llm.is_rate_limited(exc) or attempt == RATE_LIMIT_RETRIES:
                raise
            delay = min(BACKOFF_BASE_SECONDS * 2**attempt, BACKOFF_MAX_SECONDS)
            log.warning("Embedding rate-limited; retry %d in %.0fs", attempt + 1, delay)
            await _sleep(delay)
    raise AssertionError("unreachable")


async def _embed_uncached(texts: list[str]) -> list[list[float]]:
    size = get_settings().embed_batch_size
    vectors: list[list[float]] = []
    for i in range(0, len(texts), size):
        vectors.extend(await _embed_batch(texts[i : i + size]))
    return vectors


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed chunk texts; unchanged chunks come from the cache (no API call)."""
    return await cached_embed_documents(texts, _embed_uncached)


async def ingest(file_bytes: bytes, filename: str, meta: DocMeta) -> IngestResult:
    pages, warnings = await asyncio.to_thread(load_document, file_bytes, filename)
    chunks = await asyncio.to_thread(chunk_pages, pages, filename)
    if not chunks:
        warnings.append("No extractable text found; nothing was indexed")
    vectors = await embed_texts([c.text for c in chunks])
    await qdrant.delete_by_doc(meta.doc_id, meta.org_id)
    await qdrant.upsert_chunks(meta, filename, chunks, vectors)
    log.info(
        "Ingested %s (%s): %d pages, %d chunks", filename, meta.doc_id, len(pages), len(chunks)
    )
    return IngestResult(chunks=len(chunks), pages=len(pages), warnings=warnings)
