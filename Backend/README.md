# EAP Backend

REST API of the Enterprise AI Agent Platform: authentication, organizations and roles, document
upload, streaming chat, AI tools (meeting summaries, reports, emails, document insights, PDF),
admin user management, activity log and dashboard stats. It calls the AI module (`../ai`,
package `eap_ai`) in-process through `app/services/ai_gateway.py`.

FastAPI · Python 3.12 · uv · PostgreSQL 16 (SQLAlchemy 2 async + Alembic) · Redis 7 · Qdrant (via the AI module)

## Run locally

Prerequisites: Docker Desktop running and [uv](https://docs.astral.sh/uv/) installed.

```bash
cd Backend
cp .env.example .env            # then set JWT_SECRET and MISTRAL_API_KEY (see below)
docker compose up -d            # Postgres (eap + eap_test), Redis, Qdrant
uv sync                         # dependencies, incl. ../ai as an editable package
uv run alembic upgrade head     # create/upgrade the schema
uv run python scripts/seed_demo.py                      # demo org + 3 users (optional)
uv run uvicorn app.main:create_app --factory --reload   # http://127.0.0.1:8000/docs
```

Use `127.0.0.1`, not `localhost`, on Windows (avoids a ~2 s IPv6 fallback per request).
With `AI_MODE=fake` (the default) no Mistral key is needed; answers are canned but every
endpoint works, which is enough for frontend work. Set `AI_MODE=real` for real answers.

Only one Qdrant may run on port 6333: if the AI module's own stack is up, stop it first
(`docker compose down` in `../ai`).

**Demo users** (`scripts/seed_demo.py`, safe to re-run; resets the passwords):

| role | email | password |
|---|---|---|
| admin | admin@acme-demo.com | Admin@Demo2026 |
| manager | manager@acme-demo.com | Manager@Demo2026 |
| employee | employee@acme-demo.com | Employee@Demo2026 |

## Tests

```bash
docker compose up -d       # tests use the real Postgres test DB (eap_test)
uv run pytest -q           # 125 tests, offline: fake AI, fake Redis, temp storage
uv run ruff check && uv run ruff format --check .
```

The test DB is wiped and migrated once per run; every test runs in a rolled-back transaction.
`tests/test_ai_integration.py` runs the **real** AI module (orchestrator, agents, ingestion,
retrieval, PDF engine, in-memory Qdrant) with only its LLM and embedder faked: it fails if the
backend ↔ AI contract drifts, at zero API cost.
Tests refuse to run against a database whose name doesn't end in `_test`.

## API overview

- Interactive docs: **http://127.0.0.1:8000/docs**. Contract file for the frontend:
  `openapi.json` (regenerate with `uv run python scripts/export_openapi.py`).
- Everything is under `/api/v1`. Liveness: `GET /health`. Readiness: `GET /ready` checks Postgres
  and Redis, plus (with `AI_MODE=real`) the AI module's config and Qdrant; 503 if any is down.
- **Auth**: `POST /auth/login` returns `access_token` (15 min; send as `Authorization: Bearer …`;
  keep it in memory) and sets an httpOnly `refresh_token` cookie (path `/api/v1/auth`, 7 days,
  rotated on every `POST /auth/refresh`; fetch with `credentials: "include"`). A user with
  `must_change_password` gets 403 `password_change_required` everywhere except `/users/me*`.
- **Errors** always look like `{"error": {"code": "not_found", "message": "…"}}`. Other orgs'
  resources are 404, never 403.
- **Pagination**: `?limit=20&cursor=…` → `{"items": [...], "next_cursor": "…" | null}`.
- **Chat streaming**: `POST /conversations/{id}/messages` `{content, doc_ids?, force_agent?, transcript?}`
  → `text/event-stream` frames `event: status|agent|sources|token|result|error|done` + `data: <json>`,
  `: ping` every 15 s. Use `fetch` streaming (not `EventSource`: it can't POST or send headers).
  - Only **research** and **chat** stream `token`s. Meeting/email/report/document steps send
    `status` progress, then a `result` card; the final text is `done.answer`.
  - `transcript` (≤ 200k chars) enables e.g. "summarize this meeting and email the action items"
    (router runs meeting → email). `doc_ids` must be visible **and ready** (else 404 / 409).
  - `done` carries `message_id`; each `result` of that reply can be downloaded:
    `GET /conversations/{id}/messages/{message_id}/results/{index}/pdf`.
- Areas: `auth`, `users/me`, `admin/users`, `admin/activity`, `admin/stats`, `documents`,
  `conversations`, `tools/{meetings,reports,emails,documents/{id}/insights}`, `tools/generations`.

## Configuration

All settings are environment variables (or `Backend/.env`). The **same file also configures the
AI module** (`eap_ai` reads `.env` from the working directory), so it must contain the AI variables too.

| variable | default | meaning |
|---|---|---|
| `JWT_SECRET` | **required** | HMAC key for access tokens. Long random string: `uv run python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `ENV` | `dev` | `dev` / `test` / `prod` (`prod` makes the refresh cookie `Secure` → HTTPS required) |
| `LOG_LEVEL` | `INFO` | JSON logs on stdout, each line with `request_id` |
| `DATABASE_URL` | `postgresql+asyncpg://eap:eap@127.0.0.1:5432/eap` | app database |
| `TEST_DATABASE_URL` | `…/eap_test` | tests only; name must end in `_test` |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | rate limits, stats cache (+ the AI module's embedding cache) |
| `ACCESS_TOKEN_MINUTES` / `REFRESH_TOKEN_DAYS` | `15` / `7` | token lifetimes |
| `CORS_ORIGINS` | `["http://localhost:5173","http://127.0.0.1:5173"]` | JSON list of frontend origins (credentials allowed) |
| `STORAGE_BACKEND` | `local` | `local` or `s3` |
| `STORAGE_DIR` | `data/uploads` | local uploads (mount a volume in Docker) |
| `S3_BUCKET` / `S3_REGION` | — | when `STORAGE_BACKEND=s3` (AWS credentials from the usual AWS env/role) |
| `MAX_UPLOAD_MB` | `25` | document upload limit |
| `MAX_JSON_BODY_KB` | `1024` | limit for every non-upload request body |
| `AI_MODE` | `fake` | `real` calls the AI module (needs the AI variables below) |
| `LOGIN_PER_MIN` / `AI_PER_MIN` / `AI_ORG_PER_MIN` | `5` / `30` / `60` | rate limits (per IP+email / per user / per org) |
| `SSE_HEARTBEAT_SECONDS` | `15` | `: ping` interval on chat streams |
| `MISTRAL_API_KEY` | — | AI module: required when `AI_MODE=real` |
| `QDRANT_URL` | `http://127.0.0.1:6333` | AI module: vector store |
| `FAST_MODEL` / `SMART_MODEL` | `ministral-8b-latest` / `ministral-14b-latest` | AI module models |

Full list of AI-module settings (chunking, thresholds, cache): `../ai/README.md` › Configuration.

## Docker

The image installs both packages, so it is **built from the repository root**:

```bash
docker build -f Backend/Dockerfile -t eap-backend .        # run in the repo root
```

- `python:3.12-slim`, dependencies locked with uv, non-root user `app` (uid 10001),
  tiktoken tokenizer pre-downloaded. Only files whitelisted in `Backend/Dockerfile.dockerignore`
  are sent to the build, so `.env` and uploads never end up in the image.
- The entrypoint runs `alembic upgrade head`, then `uvicorn … --proxy-headers`. With
  `AI_MODE=real` the AI module (~5 s import) is loaded in the background at startup, so the
  first request after a restart isn't slow.
- Uploads live in `/app/data/uploads`: mount a volume (or use S3).

Whole stack (datastores + API container) from `Backend/`:

```bash
docker compose --profile full up -d --build
docker compose exec api python scripts/seed_demo.py
```

## Notes for deployment (Member 4)

- **One `.env`** for the backend container must include the AI module's variables
  (`MISTRAL_API_KEY`, `QDRANT_URL`, model names) plus `JWT_SECRET`, `AI_MODE=real`, `ENV=prod`.
- **SSE through Nginx**: disable buffering or tokens arrive all at once (the app also sends `X-Accel-Buffering: no`):
  ```nginx
  location /api/ {
      proxy_pass http://api:8000;
      proxy_http_version 1.1;
      proxy_buffering off;
      proxy_read_timeout 300s;          # long AI answers; the app pings every 15 s
      client_max_body_size 26m;         # uploads: MAX_UPLOAD_MB + multipart overhead
      proxy_set_header Host $host;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto $scheme;
  }
  ```
- **Client IPs** (login rate limit, activity log): set `FORWARDED_ALLOW_IPS` on the API container
  to the proxy's address. Don't set it to `*` while the API port is publicly reachable, or clients
  can spoof `X-Forwarded-For`.
- **HTTPS** is required in production (`ENV=prod` makes the refresh cookie `Secure`).
- Health checks: liveness `GET /api/v1/health`, readiness `GET /api/v1/ready`.
- Persistent volumes: Postgres, Qdrant, Redis (optional) and uploads (unless S3).
