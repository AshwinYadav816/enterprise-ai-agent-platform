"""App factory. Run: uv run uvicorn app.main:create_app --factory --reload"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import REQUEST_ID_HEADER, RequestIDMiddleware, setup_logging
from app.core.middleware import BodySizeLimitMiddleware, SecurityHeadersMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(
        title="Enterprise AI Agent Platform API",
        version="0.1.0",
        openapi_url="/api/v1/openapi.json",
        docs_url="/docs",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,  # explicit list: credentials (refresh cookie) need it
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER, "content-disposition"],
    )
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIDMiddleware)  # added last = outermost: wraps everything above
    register_error_handlers(app)
    app.include_router(api_router)
    return app
