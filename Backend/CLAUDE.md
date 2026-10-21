# EAP Backend — REST API of the Enterprise AI Agent Platform

FastAPI app that owns users, orgs, auth, documents, chat history and admin stats. It calls the
AI module only through `eap_ai.service` (sibling folder `../ai`), wrapped by `AIGateway`.

## Stack (fixed — do not swap without asking)
Python 3.12 · uv · FastAPI · Pydantic v2 + pydantic-settings · SQLAlchemy 2 async + asyncpg ·
Alembic · PyJWT · pwdlib[argon2] · redis.asyncio · boto3 (S3) · pytest + pytest-asyncio + httpx · ruff

## Layout
```
app/
  main.py            create_app(): middleware, error handlers, /api/v1 router
  core/              config, logging, errors, db, security, deps, ratelimit, pagination
  models/            SQLAlchemy models (one file per table group)
  schemas/           Pydantic request/response models (never return ORM objects)
  services/          business logic (ai_gateway, storage, documents, chat, tools, stats, audit…)
  api/v1/            thin routers: validate → call service → return schema
alembic/             migrations (never edit an applied one; add a new one)
scripts/             export_openapi.py, seed_demo.py
tests/               conftest, factories, fakes, test_*.py
docs/BACKEND_PLAN.md the phase plan
```

## Rules
- Work ONLY on the phase given in the prompt. Touch only files that phase lists (plus tests).
- Before installing a package, add it with `uv add` (never pin versions from memory). If a library
  API looks different from what you expect, read its installed source instead of guessing.
- Everything async. Type hints everywhere. Blocking work (file IO, boto3, PDF) via `asyncio.to_thread`.
- Settings (URLs, limits, TTLs, secrets) live in `core/config.py` — never hardcoded.
- **Every query on org data filters by `org_id`**; documents also by visibility
  (`allowed_roles && expand_roles(role)`). Another org's resource → 404, never 403.
- Routes return Pydantic schemas, never ORM objects. Errors use `AppError` → `{"error": {code, message}}`.
- AI calls go through `AIGateway` only. Tests use `FakeAIGateway` — never real Mistral in tests.
- `../ai` reads its settings from the current directory's `.env`: `Backend/.env` must also contain
  the AI variables (MISTRAL_API_KEY, QDRANT_URL, …).
- Run only the current phase's tests: `uv run pytest tests/<file> -q`. Run `uv run ruff check --fix` before finishing.
- Output style: no long explanations. When done, reply with: files changed, test result, anything blocked.
- Plan details: `docs/BACKEND_PLAN.md` — read only the section for the current phase.
