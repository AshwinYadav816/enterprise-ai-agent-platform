import asyncio
import logging
from typing import Annotated, Any, Protocol

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.ratelimit import get_redis
from app.services.ai_gateway import AI

router = APIRouter(tags=["health"])
log = logging.getLogger(__name__)

CHECK_TIMEOUT_SECONDS = 2.0


class Pingable(Protocol):
    async def ping(self) -> Any: ...


def get_redis_for_health() -> Pingable:
    return get_redis()


def get_engine_for_health() -> AsyncEngine:
    # Its own connection, not the request session: a dead DB must give 503, not a failed commit.
    return get_engine()


async def _select_one(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: the process is up (no dependencies checked)."""
    return {"status": "ok"}


@router.get("/ready", responses={503: {"description": "A dependency is unavailable"}})
async def ready(
    engine: Annotated[AsyncEngine, Depends(get_engine_for_health)],
    redis: Annotated[Pingable, Depends(get_redis_for_health)],
    ai: AI,
) -> JSONResponse:
    """Readiness: Postgres `SELECT 1`, Redis `PING` (2 s each); with AI_MODE=real also the AI
    module's config and its Qdrant."""
    checks: dict[str, str] = {}

    async def run(name: str, probe: Any) -> None:
        try:
            await asyncio.wait_for(probe, CHECK_TIMEOUT_SECONDS)
            checks[name] = "ok"
        except Exception as exc:
            log.warning("Readiness check %s failed: %s", name, exc)
            checks[name] = "unavailable"

    await run("database", _select_one(engine))
    await run("redis", redis.ping())
    if get_settings().ai_mode == "real":
        ai_checks = await ai.health()  # never raises
        checks["ai_config"] = ai_checks.get("config", "unknown")
        checks["qdrant"] = ai_checks.get("qdrant", "unknown")
    ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        {"status": "ready" if ok else "unavailable", "checks": checks},
        status_code=200 if ok else 503,
    )
