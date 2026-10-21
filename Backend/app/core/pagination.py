"""Keyset pagination over (timestamp, id) with an opaque cursor; newest first by default."""

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
    sort_col: InstrumentedAttribute[datetime],
    row_id: InstrumentedAttribute[uuid.UUID],
    cursor: str | None,
    limit: int,
    *,
    ascending: bool = False,
) -> Select[Any]:
    """One page ordered by (sort_col, id); fetches limit + 1 rows to detect a next page."""
    if cursor:
        t, i = decode_cursor(cursor)
        if ascending:
            stmt = stmt.where(or_(sort_col > t, and_(sort_col == t, row_id > i)))
        else:
            stmt = stmt.where(or_(sort_col < t, and_(sort_col == t, row_id < i)))
    order = (sort_col.asc(), row_id.asc()) if ascending else (sort_col.desc(), row_id.desc())
    return stmt.order_by(*order).limit(limit + 1)


def next_cursor_for(
    rows: list[Any],
    limit: int,
    key: Callable[[Any], Any] = lambda row: row,
    sort_attr: str = "created_at",
) -> str | None:
    """Call with the limit + 1 rows fetched; trims them in place and returns the next cursor.

    `key` picks the entity when rows are tuples (joined columns); `sort_attr` must match the
    column passed to paginate().
    """
    if len(rows) <= limit:
        return None
    del rows[limit:]
    last = key(rows[-1])
    return encode_cursor(getattr(last, sort_attr), last.id)
