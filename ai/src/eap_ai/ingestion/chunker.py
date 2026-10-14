"""Token-based chunking that keeps page metadata on every chunk."""

import hashlib
from collections.abc import Sequence
from functools import lru_cache

from langchain_text_splitters import RecursiveCharacterTextSplitter

from eap_ai.config import get_settings
from eap_ai.ingestion.loaders import Page
from eap_ai.vectorstore.qdrant import ChunkRecord

TIKTOKEN_ENCODING = "cl100k_base"


@lru_cache
def _splitter(chunk_size: int, chunk_overlap: int) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name=TIKTOKEN_ENCODING, chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )


def _prefix(filename: str, page: Page) -> str:
    label = page.extra.get("label") or (f"p.{page.page_no}" if page.page_no else None)
    return f"[{filename} — {label}] " if label else f"[{filename}] "


def chunk_pages(pages: Sequence[Page], filename: str) -> list[ChunkRecord]:
    s = get_settings()
    splitter = _splitter(s.chunk_size, s.chunk_overlap)
    chunks: list[ChunkRecord] = []
    for page in pages:
        prefix = _prefix(filename, page)
        for piece in splitter.split_text(page.text):
            text = prefix + piece
            chunks.append(
                ChunkRecord(
                    text=text,
                    page=page.page_no,
                    chunk_index=len(chunks),
                    content_hash=hashlib.sha256(text.encode()).hexdigest(),
                )
            )
    return chunks
