import json
import logging

import httpx
import pytest
from fastapi import FastAPI
from pydantic import BaseModel

from app.core.errors import AppError
from app.core.logging import JsonFormatter, request_id_var
from tests.conftest import TEST_ORIGIN


async def test_health_ok(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


async def test_request_id_generated_or_echoed(client: httpx.AsyncClient) -> None:
    generated = (await client.get("/api/v1/health")).headers["x-request-id"]
    assert len(generated) == 32
    echoed = await client.get("/api/v1/health", headers={"X-Request-ID": "abc-123"})
    assert echoed.headers["x-request-id"] == "abc-123"
    unsafe = await client.get("/api/v1/health", headers={"X-Request-ID": "<script>"})
    assert unsafe.headers["x-request-id"] != "<script>"  # not reflected


async def test_404_uses_error_format(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/nope")
    assert r.status_code == 404
    assert r.json() == {"error": {"code": "not_found", "message": "Not Found"}}


async def test_405_uses_error_format(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/v1/health")
    assert r.status_code == 405 and r.json()["error"]["code"] == "method_not_allowed"


class Item(BaseModel):
    name: str
    qty: int


@pytest.fixture
def app_with_test_routes(app: FastAPI) -> FastAPI:
    @app.post("/api/v1/_test/items")
    async def create_item(item: Item) -> Item:
        return item

    @app.get("/api/v1/_test/app-error")
    async def app_error() -> None:
        raise AppError("conflict", "Already exists", status=409)

    @app.get("/api/v1/_test/crash")
    async def crash() -> None:
        raise RuntimeError("db password=hunter2")

    return app


@pytest.fixture
async def test_client(app_with_test_routes: FastAPI):  # type: ignore[no-untyped-def]
    transport = httpx.ASGITransport(app=app_with_test_routes, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_validation_error_format(test_client: httpx.AsyncClient) -> None:
    r = await test_client.post("/api/v1/_test/items", json={"name": "x", "qty": "many"})
    assert r.status_code == 422
    body = r.json()["error"]
    assert body["code"] == "validation_error" and body["message"] == "Invalid request"
    assert body["details"][0]["field"] == "qty"


async def test_app_error_format(test_client: httpx.AsyncClient) -> None:
    r = await test_client.get("/api/v1/_test/app-error")
    assert r.status_code == 409
    assert r.json() == {"error": {"code": "conflict", "message": "Already exists"}}


async def test_unhandled_error_hides_details(test_client: httpx.AsyncClient) -> None:
    r = await test_client.get("/api/v1/_test/crash")
    assert r.status_code == 500
    assert r.json() == {
        "error": {"code": "internal_error", "message": "Something went wrong. Please try again."}
    }
    assert "hunter2" not in r.text and "Traceback" not in r.text


async def test_cors_allows_configured_origin_with_credentials(client: httpx.AsyncClient) -> None:
    r = await client.options(
        "/api/v1/health",
        headers={"Origin": TEST_ORIGIN, "Access-Control-Request-Method": "GET"},
    )
    assert r.headers["access-control-allow-origin"] == TEST_ORIGIN
    assert r.headers["access-control-allow-credentials"] == "true"
    other = await client.options(
        "/api/v1/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in other.headers


def test_json_log_includes_request_id() -> None:
    token = request_id_var.set("req-42")
    try:
        record = logging.LogRecord("app", logging.INFO, __file__, 1, "hello", None, None)
        line = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)
    assert line["message"] == "hello" and line["request_id"] == "req-42"
    assert line["level"] == "INFO" and "time" in line
