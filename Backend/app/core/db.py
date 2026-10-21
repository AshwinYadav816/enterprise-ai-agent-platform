"""Async engine, session factory and the request-scoped DB dependency."""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """One session per request: commit if the handler succeeded, roll back if it raised."""
    async with get_sessionmaker()() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


# scope="function": commit runs BEFORE the response is sent, so a failed commit becomes an error
# response instead of a 200 for data that was never saved. (FastAPI's default for yield
# dependencies is "request", which runs the commit after the response has gone out.)
DbSession = Annotated[AsyncSession, Depends(get_db, scope="function")]


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


def get_session_factory() -> SessionFactory:
    """For work that outlives the request (background tasks, streaming): open your own session.

    A dependency so tests can hand background work the test's rolled-back session.
    """
    return get_sessionmaker()


SessionFactoryDep = Annotated[SessionFactory, Depends(get_session_factory)]
