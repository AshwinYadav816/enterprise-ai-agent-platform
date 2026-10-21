import re
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.api.v1.health import get_engine_for_health, get_redis_for_health
from app.core.security import hash_password_async, verify_password_async
from tests.factories import make_user
from tests.fakes import PDF_BYTES

API = "/api/v1"
PASSWORD = "correct-horse-battery"

# Public by design. logout is cookie-based and idempotent (no bearer token needed).
PUBLIC = {
    ("get", "/api/v1/health"),
    ("get", "/api/v1/ready"),
    ("post", "/api/v1/auth/register"),
    ("post", "/api/v1/auth/login"),
    ("post", "/api/v1/auth/refresh"),
    ("post", "/api/v1/auth/logout"),
}


def operations(app: FastAPI) -> list[tuple[str, str, dict[str, Any]]]:
    return [
        (method, path, op)
        for path, ops in app.openapi()["paths"].items()
        if path.startswith(API)
        for method, op in ops.items()
    ]


# --- every route requires auth ------------------------------------------


async def test_every_non_public_route_requires_auth(
    app: FastAPI, client: httpx.AsyncClient, db: AsyncSession
) -> None:
    ops = operations(app)
    assert len(ops) >= 25  # sanity: the whole API is covered
    assert PUBLIC <= {(m, p) for m, p, _ in ops}  # allow-list matches real routes

    for method, path, op in ops:
        if (method, path) in PUBLIC:
            assert "security" not in op, f"{method} {path} is public but declares auth"
            continue
        assert op.get("security"), f"{method.upper()} {path} has no auth dependency"
        url = re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path)
        r = await client.request(method, url, json={})  # no Authorization header
        assert r.status_code == 401, f"{method.upper()} {path} answered {r.status_code}"


# --- security headers ------------------------------------------


async def test_security_headers_on_every_response(client: httpx.AsyncClient) -> None:
    for r in (await client.get(f"{API}/health"), await client.get(f"{API}/missing")):
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"
        assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"


# --- body limits ------------------------------------------


async def test_json_body_limit_with_content_length(client: httpx.AsyncClient) -> None:
    big = {"email": "a@acme.com", "password": "x" * (1024 * 1024)}
    r = await client.post(f"{API}/auth/login", json=big)
    assert r.status_code == 413 and r.json()["error"]["code"] == "payload_too_large"
    assert r.headers["x-frame-options"] == "DENY"


async def test_json_body_limit_when_streamed_without_length(client: httpx.AsyncClient) -> None:
    async def chunks() -> AsyncIterator[bytes]:
        yield b'{"email": "a@acme.com", "password": "'
        for _ in range(20):
            yield b"x" * 64 * 1024
        yield b'"}'

    r = await client.post(
        f"{API}/auth/login", content=chunks(), headers={"Content-Type": "application/json"}
    )
    assert r.status_code == 413 and r.json()["error"]["code"] == "payload_too_large"


async def test_uploads_may_exceed_the_json_limit(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    user = await make_user(db, password=PASSWORD)
    r = await client.post(f"{API}/auth/login", json={"email": user.email, "password": PASSWORD})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    two_mb = PDF_BYTES + b"x" * (2 * 1024 * 1024)
    up = await client.post(f"{API}/documents", headers=h, files={"file": ("big.pdf", two_mb)})
    assert up.status_code == 202, up.text


# --- readiness ------------------------------------------


async def test_ready_ok(client: httpx.AsyncClient, db: AsyncSession) -> None:
    r = await client.get(f"{API}/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ready", "checks": {"database": "ok", "redis": "ok"}}


async def test_ready_reports_redis_down(
    app: FastAPI, client: httpx.AsyncClient, db: AsyncSession
) -> None:
    class Down:
        async def ping(self) -> bool:
            raise ConnectionError("redis down")

    app.dependency_overrides[get_redis_for_health] = lambda: Down()
    r = await client.get(f"{API}/ready")
    assert r.status_code == 503
    assert r.json()["checks"] == {"database": "ok", "redis": "unavailable"}


async def test_ready_reports_database_down(
    app: FastAPI, client: httpx.AsyncClient, db: AsyncSession
) -> None:
    dead = create_async_engine("postgresql+asyncpg://eap:eap@127.0.0.1:1/none")
    app.dependency_overrides[get_engine_for_health] = lambda: dead
    try:
        r = await client.get(f"{API}/ready")
    finally:
        await dead.dispose()
    assert r.status_code == 503 and r.json()["checks"]["database"] == "unavailable"


# --- password hashing off the event loop ------------------------------------------


async def test_async_password_helpers() -> None:
    h = await hash_password_async("correct-horse-battery")
    assert h.startswith("$argon2")
    assert (await verify_password_async("correct-horse-battery", h))[0] is True
    assert (await verify_password_async("wrong", h))[0] is False
    assert (await verify_password_async("x", None))[0] is False  # unknown user path
