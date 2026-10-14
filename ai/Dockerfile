# syntax=docker/dockerfile:1
# EAP-AI package image: Python 3.12 + the eap_ai package installed into /opt/venv.
# The backend can build FROM this image, or install the same wheel. Secrets come from env vars
# at runtime (never baked in): MISTRAL_API_KEY, QDRANT_URL, ... see README "Configuration".

# --- build: resolve the locked dependencies and install the package ------------------------------
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.31 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken

WORKDIR /build

# Dependencies first (cached layer), then the project itself.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# tiktoken downloads its tokenizer on first use; fetch it now so containers need no egress for it.
RUN /opt/venv/bin/python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"

# --- runtime: slim image, non-root user ----------------------------------------------------------
FROM python:3.12-slim

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --create-home --home-dir /home/app app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/tiktoken /opt/tiktoken

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken

USER app
WORKDIR /home/app

# Smoke test by default: proves the package and its native deps import cleanly.
CMD ["python", "-c", "import eap_ai.service, eap_ai.export.pdf; print('eap-ai ready')"]
