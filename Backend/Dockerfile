# syntax=docker/dockerfile:1
# EAP backend image. Build from the REPOSITORY ROOT (the backend installs ../ai):
#   docker build -f Backend/Dockerfile -t eap-backend .
# Only files whitelisted in Backend/Dockerfile.dockerignore are sent: never .env or data/.

# --- build: locked dependencies + both packages into /opt/venv -----------------------------
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.31 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken

WORKDIR /src/Backend

# Third-party dependencies first (cached layer); the AI module's source comes after.
COPY Backend/pyproject.toml Backend/uv.lock ./
COPY ai/pyproject.toml ai/uv.lock /src/ai/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-package eap-ai

COPY ai/src /src/ai/src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# tiktoken downloads its tokenizer on first use; fetch it now so containers need no egress.
RUN /opt/venv/bin/python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"

# --- runtime ---------------------------------------------------------------------------------
FROM python:3.12-slim

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --create-home --home-dir /home/app app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/tiktoken /opt/tiktoken

WORKDIR /app
COPY Backend/app ./app
COPY Backend/alembic ./alembic
COPY Backend/alembic.ini ./
COPY Backend/scripts ./scripts
COPY Backend/docker/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod 755 /entrypoint.sh \
    && mkdir -p /app/data/uploads && chown -R app:app /app/data

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken \
    STORAGE_DIR=/app/data/uploads

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request as u; u.urlopen('http://127.0.0.1:%s/api/v1/health' % os.environ.get('PORT', '8000'), timeout=3)"
ENTRYPOINT ["/entrypoint.sh"]
