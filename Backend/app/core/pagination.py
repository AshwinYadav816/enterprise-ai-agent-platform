"""Keyset pagination over (created_at, id), newest first, with an opaque cursor."""

import base64
import binascii
import json
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import Select, and_, or_
from sqlalchemy.orm import InstrumentedAttribute

from app.core.errors import AppError

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None


def encode_cursor(created_at: datetime, row_id: uuid.UUID) -> str:
    raw = json.dumps({"t": created_at.isoformat(), "id": str(row_id)}).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded))
        return datetime.fromisoformat(data["t"]), uuid.UUID(data["id"])
    except (binascii.Error, ValueError, KeyError, TypeError) as exc:
        raise AppError("invalid_cursor", "Invalid pagination cursor", 400) from exc


LimitParam = Annotated[int, Query(ge=1, le=MAX_LIMIT)]
CursorParam = Annotated[str | None, Query(description="next_cursor from the previous page")]


def paginate(
    stmt: Select[Any],
    created_at: InstrumentedAttribute[datetime],
    row_id: InstrumentedAttribute[uuid.UUID],
    cursor: str | None,
    limit: int,
) -> Select[Any]:
    """Newest-first page; fetches limit + 1 rows so the caller can tell if there is a next page."""
    if cursor:
        t, i = decode_cursor(cursor)
        stmt = stmt.where(or_(created_at < t, and_(created_at == t, row_id < i)))
    return stmt.order_by(created_at.desc(), row_id.desc()).limit(limit + 1)


def next_cursor_for(
    rows: list[Any], limit: int, key: Callable[[Any], Any] = lambda row: row
) -> str | None:
    """Call with the limit + 1 rows fetched; trims them in place and returns the next cursor.

    `key` picks the entity carrying created_at/id when rows are tuples (e.g. joined columns).
    """
    if len(rows) <= limit:
        return None
    del rows[limit:]
    last = key(rows[-1])
    return encode_cursor(last.created_at, last.id)
