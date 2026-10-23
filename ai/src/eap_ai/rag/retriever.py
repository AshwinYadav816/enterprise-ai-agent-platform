"""Retrieval: embed -> filtered dense search -> threshold -> MMR -> token budget."""

import asyncio
import math
from collections.abc import Sequence
from functools import lru_cache

import tiktoken
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from qdrant_client import models

from eap_ai import llm
from eap_ai.cache import cached_embed_query
from eap_ai.config import get_settings
from eap_ai.ingestion.chunker import TIKTOKEN_ENCODING
from eap_ai.rag.prompts import REWRITE_SYSTEM, rewrite_user_message
from eap_ai.schemas import ChatMessage, Source, UserCtx
from eap_ai.vectorstore import qdrant

REWRITE_HISTORY_MESSAGES = 6


class StandaloneQuestion(BaseModel):
    question: str = Field(description="The follow-up rewritten as a self-contained question")


@lru_cache
def _encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding(TIKTOKEN_ENCODING)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def mmr(
    query_vec: Sequence[float],
    vectors: Sequence[Sequence[float]],
    k: int,
    lambda_mult: float,
) -> list[int]:
    """Maximal marginal relevance: indices of k items balancing relevance and diversity."""
    if not vectors:
        return []
    relevance = [_cosine(query_vec, v) for v in vectors]
    selected: list[int] = []
    remaining = list(range(len(vectors)))
    while remaining and len(selected) < k:

        def score(i: int) -> float:
            redundancy = max((_cosine(vectors[i], vectors[j]) for j in selected), default=0.0)
            return lambda_mult * relevance[i] - (1 - lambda_mult) * redundancy

        best = max(remaining, key=score)
        selected.append(best)
        remaining.remove(best)
    return selected


def _vector(point: models.ScoredPoint) -> list[float]:
    v = point.vector
    if isinstance(v, dict):  # named vectors: take the first
        v = next(iter(v.values()))
    return list(v) if v is not None else []  # type: ignore[arg-type]


async def rewrite_query(query: str, history: Sequence[ChatMessage]) -> str:
    """Turn a follow-up into a standalone question. No LLM call when history is empty."""
    if not history:
        return query
    recent = history[-REWRITE_HISTORY_MESSAGES:]
    history_text = "\n".join(f"{m.role}: {m.content}" for m in recent)
    model = llm.get_chat_model("rewrite").with_structured_output(StandaloneQuestion)
    result = await model.ainvoke(
        [
            SystemMessage(content=REWRITE_SYSTEM),
            HumanMessage(content=rewrite_user_message(query, history_text)),
        ]
    )
    assert isinstance(result, StandaloneQuestion)
    return result.question.strip() or query


async def retrieve(query: str, user: UserCtx, doc_ids: Sequence[str] | None = None) -> list[Source]:
    """Sources the user may see, most relevant and diverse first, within the token budget."""
    s = get_settings()
    query_vec = await cached_embed_query(query)
    hits = await qdrant.search(
        query_vec, user.org_id, user.roles, doc_ids=doc_ids, limit=s.top_k, with_vectors=True
    )
    hits = [h for h in hits if h.score >= s.score_threshold]
    order = mmr(query_vec, [_vector(h) for h in hits], s.final_k, s.mmr_lambda)

    enc = await asyncio.to_thread(_encoding)  # first call may download the tokenizer
    sources: list[Source] = []
    used = 0
    for i in order:
        payload = hits[i].payload or {}
        text = str(payload.get("text", ""))
        tokens = len(enc.encode(text))
        if sources and used + tokens > s.max_context_tokens:
            break
        used += tokens
        sources.append(
            Source(
                n=len(sources) + 1,
                doc_id=str(payload.get("doc_id", "")),
                filename=str(payload.get("filename", "")),
                page=payload.get("page"),
                snippet=text,
            )
        )
    return sources
