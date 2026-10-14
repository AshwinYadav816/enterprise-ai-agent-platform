"""Qdrant access. Every read filters by org_id AND the caller's roles."""

import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from qdrant_client import AsyncQdrantClient, models

from eap_ai.config import get_settings
from eap_ai.llm import embedding_dim
from eap_ai.schemas import DocMeta

_POINT_NS = uuid.UUID("6f1c2a52-3d0e-4a8f-9a57-4c3e8b0f2d11")
_KEYWORD_INDEXES = ("org_id", "doc_id", "allowed_roles")
_SCROLL_PAGE = 256

_client: AsyncQdrantClient | None = None
_ready: set[str] = set()


@dataclass(frozen=True)
class ChunkRecord:
    """One chunk ready for storage (text already carries the filename/page prefix)."""

    text: str
    page: int | None
    chunk_index: int
    content_hash: str


def get_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        s = get_settings()
        if s.qdrant_url == ":memory:":
            _client = AsyncQdrantClient(location=":memory:")
        else:
            key = s.qdrant_api_key.get_secret_value() if s.qdrant_api_key else None
            _client = AsyncQdrantClient(url=s.qdrant_url, api_key=key)
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.close()
    _client = None
    _ready.clear()


def point_id(org_id: str, doc_id: str, chunk_index: int) -> str:
    """Deterministic ID so re-ingesting a document overwrites its points."""
    return str(uuid.uuid5(_POINT_NS, f"{org_id}:{doc_id}:{chunk_index}"))


async def collection_name() -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", get_settings().embedding_model.lower()).strip("_")
    return f"docs_{slug}_{await embedding_dim()}"


async def ensure_collection() -> str:
    name = await collection_name()
    if name in _ready:
        return name
    client = get_client()
    if not await client.collection_exists(name):
        await client.create_collection(
            name,
            vectors_config=models.VectorParams(
                size=await embedding_dim(), distance=models.Distance.COSINE
            ),
        )
        for field in _KEYWORD_INDEXES:
            await client.create_payload_index(name, field, models.PayloadSchemaType.KEYWORD)
    _ready.add(name)
    return name


def _access_filter(
    org_id: str, roles: Sequence[str], doc_ids: Sequence[str] | None = None
) -> models.Filter:
    must: list[models.Condition] = [
        models.FieldCondition(key="org_id", match=models.MatchValue(value=org_id)),
        models.FieldCondition(key="allowed_roles", match=models.MatchAny(any=list(roles))),
    ]
    if doc_ids:
        must.append(models.FieldCondition(key="doc_id", match=models.MatchAny(any=list(doc_ids))))
    return models.Filter(must=must)


def _doc_filter(org_id: str, doc_id: str) -> models.Filter:
    return models.Filter(
        must=[
            models.FieldCondition(key="org_id", match=models.MatchValue(value=org_id)),
            models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id)),
        ]
    )


async def upsert_chunks(
    meta: DocMeta, filename: str, chunks: Sequence[ChunkRecord], vectors: Sequence[list[float]]
) -> None:
    if len(chunks) != len(vectors):
        raise ValueError("chunks and vectors length mismatch")
    if not chunks:
        return
    name = await ensure_collection()
    points = [
        models.PointStruct(
            id=point_id(meta.org_id, meta.doc_id, c.chunk_index),
            vector=v,
            payload={
                "org_id": meta.org_id,
                "doc_id": meta.doc_id,
                "owner_id": meta.owner_id,
                "allowed_roles": meta.allowed_roles,
                "filename": filename,
                "page": c.page,
                "chunk_index": c.chunk_index,
                "text": c.text,
                "content_hash": c.content_hash,
            },
        )
        for c, v in zip(chunks, vectors, strict=True)
    ]
    await get_client().upsert(name, points=points, wait=True)


async def delete_by_doc(doc_id: str, org_id: str) -> None:
    """Delete all points of a document. Scoped to org_id so one org can't delete another's."""
    name = await ensure_collection()
    await get_client().delete(
        name, points_selector=models.FilterSelector(filter=_doc_filter(org_id, doc_id)), wait=True
    )


async def search(
    vector: list[float],
    org_id: str,
    roles: Sequence[str],
    doc_ids: Sequence[str] | None = None,
    limit: int | None = None,
    with_vectors: bool = False,
) -> list[models.ScoredPoint]:
    """Dense search restricted to the user's org and roles (any-of)."""
    if not roles:
        return []
    name = await ensure_collection()
    res = await get_client().query_points(
        name,
        query=vector,
        query_filter=_access_filter(org_id, roles, doc_ids),
        limit=limit or get_settings().top_k,
        with_payload=True,
        with_vectors=with_vectors,
    )
    return res.points


async def scroll_doc(doc_id: str, org_id: str, roles: Sequence[str]) -> list[models.Record]:
    """All chunks of one document the user may see, ordered by chunk_index."""
    if not roles:
        return []
    name = await ensure_collection()
    client = get_client()
    flt = _access_filter(org_id, roles, [doc_id])
    records: list[models.Record] = []
    offset: models.ExtendedPointId | None = None
    while True:
        page, offset = await client.scroll(
            name, scroll_filter=flt, limit=_SCROLL_PAGE, offset=offset, with_payload=True
        )
        records.extend(page)
        if offset is None:
            break
    records.sort(key=lambda r: (r.payload or {}).get("chunk_index", 0))
    return records
