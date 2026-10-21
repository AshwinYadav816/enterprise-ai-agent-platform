"""Security headers and a request-body size limit (pure ASGI: safe for SSE streaming)."""

import json
import re

from fastapi import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings
from app.core.errors import error_body

SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
]

# Routes that legitimately carry files or long transcripts; everything else is small JSON.
UPLOAD_PATHS = re.compile(r"^/api/v1/(documents|tools/meetings|conversations/[^/]+/messages)/?$")


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                present = {k.lower() for k, _ in message.get("headers", [])}
                extra = [(k, v) for k, v in SECURITY_HEADERS if k not in present]
                message["headers"] = [*message.get("headers", []), *extra]
            await send(message)

        await self.app(scope, receive, send_with_headers)


class _BodyTooLarge(HTTPException):
    """An HTTPException so FastAPI's body parser re-raises it (it wraps other errors as 400)
    and our error handler renders it in the standard format."""

    code = "payload_too_large"  # same code as the early Content-Length rejection

    def __init__(self, limit: int) -> None:
        super().__init__(413, f"Request body is larger than {limit // 1024} KB")


class BodySizeLimitMiddleware:
    """413 for bodies over the limit: early via Content-Length, else while reading (chunked)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    @staticmethod
    def limit_for(path: str) -> int:
        s = get_settings()
        if UPLOAD_PATHS.match(path):
            return (s.max_upload_mb + 1) * 2**20  # +1 MB for multipart overhead
        return s.max_json_body_kb * 1024

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS", "DELETE"):
            await self.app(scope, receive, send)
            return
        limit = self.limit_for(scope["path"])
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > limit:
            await self._reject(send, limit)
            return

        received = 0
        started = False

        async def counting_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _BodyTooLarge(limit)
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except _BodyTooLarge:
            if not started:
                await self._reject(send, limit)

    @staticmethod
    async def _reject(send: Send, limit: int) -> None:
        body = json.dumps(
            error_body("payload_too_large", f"Request body is larger than {limit // 1024} KB")
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    *SECURITY_HEADERS,
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
