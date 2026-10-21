# Backend Development Plan — Enterprise AI Agent Platform
Owner: Member 2 (Backend Development) · Scope: REST APIs, authentication, database design, business logic, chat services
Works with: Member 1 (frontend calls these APIs) · Member 3 (AI module `eap_ai`) · Member 4 (Docker, CI, deploy)

> **Repo notes (2026-10-22):** the backend lives in `Backend/` (next to `ai/`). The AI module is
> complete (AI phases 0–10), so every backend phase can use the real AI. Review adjustments are in
> **Part G**; apply them in the phase they name.

---

## Part A — How to use this with Claude Code (read once)

**Setup**
1. `Backend/CLAUDE.md` holds the rules; this file is `Backend/docs/BACKEND_PLAN.md`.
2. Open Claude Code inside `Backend/`.
3. Run **one phase per session.** Paste only that phase's "Prompt" block.
4. When the phase's "Done when" checks pass, commit on `main` in the team's usual order:
   `git add Backend` → `git commit` → `git pull --rebase origin main` → `git push`. Then run `/clear` and start the next phase.

**Why this saves tokens**
- `CLAUDE.md` is short and auto-loaded; the plan is read one section at a time.
- `/clear` between phases stops old context being re-sent with every message.
- Each prompt lists exact files, so Claude Code doesn't explore the repo.
- AI calls are faked in tests → no Mistral spend, tests run in seconds.
- Use plan mode (Shift+Tab) for Phase 5 (chat streaming): approve the design before code is written.
- Long session? `/compact`, don't restart. Failing test? Paste the exact output and say "fix this".

**Your checks after every phase (2 minutes)**
- `uv run pytest -q` green · `uv run ruff check` clean · `uv run alembic upgrade head` works on an empty DB.
- Skim the diff: every query on org data filters by `org_id`; no secrets or hardcoded URLs; no ORM objects returned directly.
- Open http://localhost:8000/docs and try the new endpoints once by hand.

**Dependency order with other members**
| Backend phase | Needs |
|---|---|
| 0–3 | Nothing — start immediately |
| 4 (AI gateway + documents) | AI module ✅ done |
| 5 (chat) | AI module ✅ done |
| 6 (tools) | AI module ✅ done |
| Hand to Member 1 | `openapi.json` after Phase 2, and again after every phase |

---

## Part B — Architecture decisions (already made)

| Decision | Choice | Reason |
|---|---|---|
| Structure | Routers → services → models; one API version prefix `/api/v1` | Thin routes, testable logic, easy to explain in viva |
| DB access | SQLAlchemy 2.0 async + asyncpg; Alembic migrations | Industry standard; migrations show proper DB design |
| IDs | UUID primary keys (uuid4), `created_at` timestamptz on every table | Safe to expose in URLs, no enumeration |
| Multi-tenancy | `organizations` table; every user/document/conversation has `org_id` | PRD says "enterprise"; also matches the AI module's `org_id` filter |
| Sign-up | `POST /auth/register` creates a new org + its first **admin**. Admins create other users (temporary password, must change on first login) | Simple, demo-able, no email service needed |
| Roles | `admin`, `manager`, `employee`, hierarchical (see `expand_roles`) | One rule shared by API permissions and document visibility |
| Passwords | Argon2 via `pwdlib` | Current FastAPI recommendation; passlib is unmaintained |
| Tokens | Access JWT (HS256, 15 min) returned in JSON, sent as `Authorization: Bearer`. Refresh token (random, 7 days) in an **httpOnly cookie** scoped to `/api/v1/auth`, stored **hashed** in DB, rotated on every refresh | Access token never in localStorage; refresh can be revoked (logout, deactivate) |
| Document visibility | Uploader picks `visibility` = employee \| manager \| admin → stored as `allowed_roles=[visibility]`; a user sees a doc if `allowed_roles && expand_roles(user.role)` | Same rule in Postgres and in Qdrant; admins see everything |
| File storage | `Storage` interface: local disk in dev, S3 in prod (`STORAGE_BACKEND=local\|s3`) | Matches PRD (AWS S3) without needing AWS during development |
| Ingestion | Upload → save file → row `status=processing` → background task calls `ai.ingest_document` → `ready`/`failed`. Frontend polls `GET /documents/{id}` | Upload returns instantly; FastAPI BackgroundTasks is enough at this scale |
| Chat history | **Backend owns it** (Postgres). Per turn: send last 6 messages + rolling `summary`; when unsummarized messages > 12, call `ai.summarize_history` and store the new summary | Agreed contract with the AI module |
| Streaming | `POST /conversations/{id}/messages` returns `text/event-stream`; each AI `Event` → one SSE `event:`/`data:` frame. Heartbeat every 15 s. Header `X-Accel-Buffering: no` | Real-time streaming (PRD 5.2); works through Nginx |
| Tools (meeting/report/email/document) | Dedicated JSON endpoints that call `ai.run` with `force_agent`, collect the `result` event, save to a single `generations` table | One table + one service for four features = less code |
| PDF export | `ai.export_pdf(markdown, title)` in `asyncio.to_thread`; markdown built by `services/markdown.py` | AI module owns the PDF engine; backend only renders markdown |
| Usage stats | Store `prompt_tokens`, `completion_tokens`, `agent` from the AI `done` event on messages and generations | Admin dashboard "AI usage statistics" with no extra service |
| Activity logs | `audit_logs` table written by `audit.log(...)` on key actions | Admin dashboard "system activity logs" |
| Rate limiting | Redis fixed window: login 5/min per IP+email, AI endpoints 30/min per user. If Redis is down: allow and log a warning | Protects Mistral quota; never takes the app down |
| Errors | One format: `{"error": {"code": "not_found", "message": "..."}}` | Frontend handles errors in one place |
| Testing | Real Postgres test DB (`eap_test`) from docker compose, each test in a rolled-back transaction; `FakeAIGateway` via dependency override | Postgres-specific features (arrays, JSONB) behave exactly as in prod |

### Database schema
```
organizations  id, name, created_at
users          id, org_id→organizations, email (unique, lowercased), password_hash, full_name,
               role enum(admin,manager,employee), is_active, must_change_password,
               last_login_at, created_at
refresh_tokens id, user_id→users (cascade), token_hash (unique), expires_at, revoked_at, created_at
documents      id, org_id, owner_id→users, filename, content_type, size_bytes, storage_key,
               allowed_roles text[], status enum(processing,ready,failed), chunk_count, page_count,
               warnings jsonb, error text, created_at, updated_at
               index (org_id, created_at desc); GIN index on allowed_roles
conversations  id, org_id, user_id, title, summary text, summarized_count int default 0,
               created_at, updated_at       index (user_id, updated_at desc)
messages       id, conversation_id→conversations (cascade), role enum(user,assistant),
               content text, agent text null, sources jsonb, results jsonb,
               status enum(complete,interrupted,error), prompt_tokens, completion_tokens, created_at
               index (conversation_id, created_at)
generations    id, org_id, user_id, kind enum(meeting,report,email,document_insights), title,
               input jsonb, output jsonb, markdown text, prompt_tokens, completion_tokens, created_at
               index (org_id, kind, created_at desc)
audit_logs     id, org_id, user_id null, action text, target_type text null, target_id uuid null,
               meta jsonb, ip text null, created_at   index (org_id, created_at desc)
```

### API contract (share with Member 1 — all under `/api/v1`)
| Method & path | Who | Purpose |
|---|---|---|
| GET `/health`, `/ready` | public | liveness; readiness checks DB + Redis |
| POST `/auth/register` | public | create org + admin, returns tokens |
| POST `/auth/login` | public | email+password → `{access_token, user}` + refresh cookie |
| POST `/auth/refresh` | cookie | rotate refresh, new access token |
| POST `/auth/logout` | cookie | revoke refresh, clear cookie |
| GET / PATCH `/users/me` | any | profile (full_name) |
| POST `/users/me/password` | any | change password (clears `must_change_password`, revokes other sessions) |
| GET / POST `/admin/users` | admin | list (search, role filter, pagination) / create user with temp password |
| PATCH `/admin/users/{id}` | admin | change role, activate/deactivate (deactivate revokes refresh tokens) |
| GET `/admin/stats` | admin | users by role, docs count + storage bytes, conversations, messages, tokens per day (30 d) + per agent |
| GET `/admin/activity` | admin | audit log, paginated, filter by action/user |
| POST `/documents` | any | multipart: `file`, `visibility` → 202 + document (status processing) |
| GET `/documents` | any | list visible docs, filter status, search filename, pagination |
| GET `/documents/{id}` | visible | detail incl. status (poll this) |
| GET `/documents/{id}/download` | visible | file stream (or S3 presigned redirect) |
| DELETE `/documents/{id}` | owner or admin | removes vectors, file, row |
| GET / POST `/conversations` | any | list own / create |
| PATCH / DELETE `/conversations/{id}` | owner | rename / delete |
| GET `/conversations/{id}/messages` | owner | history, cursor pagination (oldest→newest) |
| POST `/conversations/{id}/messages` | owner | `{content, doc_ids?, force_agent?}` → **SSE stream** |
| POST `/tools/meetings` | any | transcript text or file (.txt/.vtt/.docx) → MeetingSummary |
| POST `/tools/reports` | any | `{report_type, period, instruction, doc_ids?}` → Report |
| POST `/tools/emails` | any | `{task, tone?, text}` → EmailOutput |
| POST `/tools/documents/{id}/insights` | visible | → DocumentInsights |
| GET `/tools/generations` | any | own history, filter `kind` |
| GET `/tools/generations/{id}` | owner | detail |
| GET `/tools/generations/{id}/pdf` | owner | PDF download |

**SSE format** (frontend uses `fetch` + a stream reader, e.g. `@microsoft/fetch-event-source`, because `EventSource` can't send POST or the auth header):
```
event: status|agent|token|sources|result|error|done
data: {"...": "..."}          ← the AI Event's data, JSON
: ping                        ← heartbeat comment every 15 s
```
The `done` frame also carries `{"message_id": "<saved assistant message id>"}`.

**Pagination** everywhere: `?limit=20&cursor=<opaque>` → `{"items": [...], "next_cursor": "..."|null}`.

---

## Part C — Phases

Estimated ~7 weeks part-time. Phases 0–3 = working auth app; 4–6 = all PRD features; 7–8 = dashboard and production readiness.

### Phase 0 — Project skeleton
**Prompt:**
> Phase 0. Read Part B of the plan once. Set up the project per CLAUDE.md layout with uv (Python 3.12). Deps: fastapi, uvicorn[standard], pydantic-settings, sqlalchemy[asyncio], asyncpg, alembic, pyjwt, pwdlib[argon2], python-multipart, email-validator, redis, boto3; dev: pytest, pytest-asyncio, httpx, ruff. Add the AI module as editable path dependency (`uv add --editable ../ai`); if `../ai` has no pyproject yet, skip it and note that in your reply.
> - `core/config.py`: Settings — env (dev|test|prod), database_url, test_database_url, redis_url, jwt_secret (SecretStr), access_token_minutes=15, refresh_token_days=7, cors_origins (list), storage_backend (local|s3), storage_dir, s3_bucket, s3_region, max_upload_mb=25, allowed_extensions [pdf,docx,pptx,xlsx], ai_mode (fake|real), rate limits (login_per_min=5, ai_per_min=30).
> - `core/logging.py`: JSON logs via stdlib logging; middleware adding `X-Request-ID` (incoming or new uuid) to response + log records.
> - `core/errors.py`: `AppError(code, message, status)` + handlers for AppError, RequestValidationError, HTTPException, and unhandled Exception (500, no stack trace in response) — all in the `{"error": {...}}` format.
> - `main.py`: `create_app()` with CORS (allow_credentials=True, explicit origins), handlers, `/api/v1` router with `health.py` (GET /health → {"status":"ok"}).
> - `docker-compose.yml`: postgres:16 (creates `eap` and `eap_test` DBs via an init script), redis:7, named volumes.
> - `.env.example`, `.gitignore`, ruff config (line-length 100, select E,F,I,UP,B,ASYNC), pytest config in pyproject (`asyncio_mode = "auto"`; set the asyncio default fixture/test loop scope to session — check the installed pytest-asyncio docs for the exact option names).
> - `tests/conftest.py` with an httpx AsyncClient over ASGITransport; `tests/test_health.py` (health ok, error format for 404 and validation error).

**Done when:** `docker compose up -d` runs Postgres + Redis, `uv run uvicorn app.main:create_app --factory --reload` serves http://localhost:8000/docs, tests pass.

### Phase 1 — Database models + migrations
**Prompt:**
> Phase 1. Read the "Database schema" in Part B. Files: `core/db.py`, all `models/*.py`, `alembic/` (async env), `tests/conftest.py` (extend), `tests/test_models.py`.
> - `core/db.py`: async engine + `async_sessionmaker(expire_on_commit=False)`; dependency `get_db()` yields a session and commits on success / rolls back on error.
> - `models/base.py`: DeclarativeBase with a naming convention for constraints (so Alembic names are stable), mixin for `id` (UUID, default uuid4) and `created_at` (timestamptz, server default now()); `updated_at` where the schema lists it.
> - Models exactly per schema: Postgres ENUM types, ARRAY(Text) for allowed_roles, JSONB columns, FKs with ondelete as listed, all listed indexes (GIN on allowed_roles).
> - Alembic: async env.py reading `database_url` from Settings, `target_metadata` from models; generate the initial migration and check it creates enums and indexes.
> - Test fixtures: session-scoped engine on `test_database_url` that runs `alembic upgrade head` once (drop all first); per-test session joined to an outer connection/transaction that is rolled back (SQLAlchemy `join_transaction_mode="create_savepoint"`); override `get_db` in the app. Factory helpers `make_org`, `make_user(role=...)` in `tests/factories.py`.
> - Tests: create org+user, unique email violation, cascade delete conversation → messages.

**Done when:** `uv run alembic upgrade head` on the `eap` DB creates all tables (check with a DB client), `alembic downgrade base` works, tests pass.

### Phase 2 — Authentication + RBAC
**Prompt:**
> Phase 2. Read Part B rows "Sign-up", "Roles", "Passwords", "Tokens". Files: `core/security.py`, `core/deps.py`, `core/ratelimit.py`, `services/auth.py`, `schemas/auth.py`, `schemas/users.py`, `api/v1/auth.py`, `api/v1/users.py`, `tests/test_auth.py`.
> - security: hash/verify with pwdlib Argon2; `create_access_token(user)` (claims: sub, org, role, exp, iat, type="access"); `decode_access_token` → AppError 401 on invalid/expired; refresh token = `secrets.token_urlsafe(48)`, store sha256 hash only; `expand_roles(role)`.
> - deps: `get_current_user` (Bearer → load user, must be active), `require_roles(*roles)` dependency factory, `client_ip(request)`.
> - ratelimit: `async def hit(key, limit, window_s)` using Redis INCR + EXPIRE; fail open with a logged warning if Redis errors; dependency `rate_limit("login")` / `rate_limit("ai")`.
> - auth service + routes: register (org name, full name, email, password ≥ 8 chars) → org + admin; login (generic "Invalid email or password" for both wrong email and wrong password; inactive → 403; updates last_login_at); refresh (rotate: revoke old, issue new; reuse of a revoked token revokes ALL the user's tokens); logout. Refresh cookie: httpOnly, SameSite=Lax, Secure when env=prod, path `/api/v1/auth`. Login response includes `must_change_password`.
> - users routes: GET/PATCH `/users/me`, POST `/users/me/password` (verify current, set new, clear must_change_password, revoke other refresh tokens).
> - Tests: register→login→me; wrong password 401; expired/garbled token 401; refresh rotation and reuse detection; logout invalidates refresh; inactive user blocked; login rate limit returns 429 (use a fake/in-memory Redis via dependency override or a test Redis DB — no sleeps).

**Done when:** tests pass; in Swagger you can register, log in, call `/users/me`. Export `openapi.json` (`uv run python -c "..."` script in `scripts/export_openapi.py`) and give it to Member 1.

### Phase 3 — Admin user management + audit log
**Prompt:**
> Phase 3. Files: `services/users.py`, `services/audit.py`, `schemas/admin.py`, `api/v1/admin.py` (users + activity only — stats come in Phase 7), `core/pagination.py`, `tests/test_admin_users.py`.
> - pagination: cursor helper encoding (created_at, id) as base64; `Page[T]` schema `{items, next_cursor}`.
> - audit: `async def log(db, *, org_id, user_id, action, target_type=None, target_id=None, meta=None, ip=None)` — adds a row in the same transaction. Call it now from: register, login success, login failed (user_id null, meta email), password change, user created, role changed, user deactivated.
> - admin routes (require admin): GET /admin/users (search email/name, role filter, paginated); POST /admin/users (email, full_name, role) → generates a temporary password, returns it ONCE in the response, sets must_change_password; PATCH /admin/users/{id} (role, is_active). Guards: admin cannot demote or deactivate themselves; cannot remove the org's last active admin; only same-org users (other org → 404, not 403).
> - GET /admin/activity: paginated, filters action and user_id.
> - Tests: non-admin gets 403; cross-org access 404; last-admin guard; deactivation revokes refresh tokens; audit rows written.

**Done when:** tests pass; an admin can create a manager and an employee, and both can log in and change their temp password.

### Phase 4 — AI gateway + storage + documents
**Prompt:**
> Phase 4. Prerequisite: `eap_ai.schemas` exists (AI Phase 1). Files: `services/ai_gateway.py`, `services/storage.py`, `services/documents.py`, `schemas/documents.py`, `api/v1/documents.py`, `tests/fakes.py`, `tests/test_documents.py`.
> - ai_gateway: `AIGateway` Protocol mirroring `eap_ai.service` (ingest_document, delete_document, run, summarize_history, export_pdf). `RealAIGateway` imports `eap_ai.service` lazily inside methods (so the app starts without Mistral keys in fake mode); `FakeAIGateway` in the same file for local dev: ingest returns a fixed IngestResult, run yields status → sources → a few token events → result (if force_agent) → done with usage, export_pdf returns a minimal valid PDF. Dependency `get_ai()` picks by `settings.ai_mode`. Helper `user_ctx(user) -> UserCtx` using `expand_roles`. Use types from `eap_ai.schemas` — do not redefine them.
> - storage: `Storage` Protocol (save(key, bytes), open(key) → bytes, delete(key), url_or_none(key)). `LocalStorage` (storage_dir, run file IO in `asyncio.to_thread`, refuse keys with `..`), `S3Storage` (boto3 in to_thread, presigned GET 5 min). Key = `{org_id}/{document_id}/{safe_filename}`.
> - documents service + routes per the API table. Upload: validate extension AND size (read in chunks, stop at max_upload_mb → 413), sanitize filename, visibility → allowed_roles, save file, insert row status=processing, commit, then BackgroundTask `process_document(doc_id)` that opens its OWN db session, reads the file, calls `ai.ingest_document(bytes, filename, DocMeta)`, sets ready + counts + warnings, or failed + short error message (log the full exception). List/detail/download apply org + visibility filter (`allowed_roles && expand_roles(role)`); invisible = 404. Delete: owner or admin; call ai.delete_document, storage delete, row delete; audit log for upload/delete.
> - Tests (FakeAIGateway + LocalStorage in tmp_path): upload → processing → ready; bad extension 400; too large 413; employee can't see manager-only doc (404) while admin can; other org 404; delete permissions; failed ingest sets status failed.

**Done when:** tests pass; with `AI_MODE=real`, uploading a real PDF ends `ready` and its chunks appear in the Qdrant dashboard.

### Phase 5 — Chat with streaming — use plan mode
**Prompt:**
> Phase 5. Enter plan mode first and show me the design (especially the streaming + save flow) before writing code. Read Part B rows "Chat history" and "Streaming" and the SSE format. Files: `services/chat.py`, `schemas/chat.py`, `api/v1/conversations.py`, `tests/test_chat.py`.
> - Conversation CRUD per API table, owner-only (others → 404). Messages list: cursor pagination, oldest→newest.
> - POST messages flow: (1) rate_limit("ai"); (2) validate doc_ids are visible to the user; (3) save user message and commit; if it's the first message set title = first 60 chars (no LLM call); (4) build context: if unsummarized messages (total − summarized_count, excluding the new one) > 12 → `ai.summarize_history` over [previous summary as a system message] + all messages except the last 6, store summary and summarized_count; history = last 6 messages; (5) build AgentRequest (query, user_ctx, history, history_summary, force_agent, doc_ids); (6) stream `ai.run` events as SSE frames, collecting token text, sources, agent names, result payloads and usage; (7) after the stream ends, save the assistant message (status complete / error) with a NEW db session — the request session may already be closed while streaming — and send `done` with message_id.
> - Robustness: heartbeat `: ping` every 15 s while waiting for events; if the client disconnects (`request.is_disconnected()` or CancelledError) save what was generated with status interrupted, then stop; exceptions from AI → `error` frame with a safe message, saved status error. Headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`.
> - Use StreamingResponse with `media_type="text/event-stream"` and a small `sse_frame(event, data)` formatter (JSON with `ensure_ascii=False`).
> - Tests with FakeAIGateway: frames arrive in order and assistant message is saved with tokens and usage; summarization triggers after 13 messages and is not re-run next turn; another user's conversation 404; invisible doc_id 404; AI error produces error frame + saved error message.

**Done when:** tests pass; `curl -N -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"content":"hi"}' http://127.0.0.1:8000/api/v1/conversations/<id>/messages` streams tokens live; with `AI_MODE=real` you get cited answers from uploaded docs.

### Phase 6 — Tools: meetings, reports, emails, document insights, PDF
**Prompt:**
> Phase 6. Files: `services/tools.py`, `services/markdown.py`, `schemas/tools.py`, `api/v1/tools.py`, `tests/test_tools.py`.
> - One core function `run_tool(db, ai, user, kind, agent, query, transcript=None, doc_ids=None, title)`: rate_limit ai, builds AgentRequest with `force_agent`, consumes `ai.run`, takes the LAST `result` event as output (no result or an error event → AppError 502 "AI could not complete this request"), saves a `generations` row with input, output, markdown, usage; audit log; returns the generation.
> - Endpoints per API table:
>   - meetings: JSON `{transcript, title?}` or multipart file (.txt, .vtt, .docx; docx text via python-docx — add it with uv) ; transcript max 200k chars.
>   - reports: `{report_type: weekly|monthly|sprint|project, period: str, instruction, doc_ids?}`; doc_ids visibility-checked; query = clear instruction text including type and period.
>   - emails: `{task: draft|rewrite|grammar|tone|summarize_thread, tone?: formal|friendly|concise|persuasive, text}` → query "Task: … Tone: …\n\n<text>".
>   - document insights: doc must be visible and status ready (else 409).
> - markdown.py: `render(kind, output: dict) -> str` for each kind (meeting: summary, decisions, action-item table with owner/due; report: sections, highlights, risks, next steps; email: subject + body; insights). Pure functions.
> - generations list/detail (owner-only, filter kind, paginated) and `/pdf`: `ai.export_pdf(markdown, title)` in `asyncio.to_thread`, return `application/pdf` with `Content-Disposition: attachment; filename="<slug>.pdf"`.
> - Tests with FakeAIGateway: each tool saves a generation and returns its output; missing result → 502; PDF endpoint returns bytes starting with `%PDF`; markdown render for each kind (snapshot-style asserts on key lines).

**Done when:** tests pass; with real AI, a pasted transcript returns decisions + action items and the PDF downloads and opens.

### Phase 7 — Admin dashboard stats
**Prompt:**
> Phase 7. Files: `services/stats.py`, extend `schemas/admin.py` and `api/v1/admin.py`, `tests/test_admin_stats.py`. GET /admin/stats (admin, own org) returning: users total + by role + active in last 7 days; documents total + by status + total storage bytes; conversations total; messages total; generations by kind; tokens (prompt+completion) per day for the last 30 days from messages + generations (fill missing days with 0); tokens and request count per agent. Use aggregate SQL queries (`func.count`, `func.sum`, `date_trunc`) — no loading rows into Python; at most ~6 queries; run them sequentially on the same session. Cache the response in Redis for 60 s per org (skip cache on Redis error). Tests: numbers correct on seeded data; other org's data never counted; non-admin 403.

**Done when:** tests pass; Member 1 can build the dashboard charts from one call.

### Phase 8 — Hardening, Docker, handover
**Prompt:**
> Phase 8. Review + small additions only, no new features. (1) Check every service for: queries missing org_id or visibility filters, ORM objects leaking from routes, missing auth dependencies on routes (write a test that iterates `app.routes` and asserts every `/api/v1` route except health/auth/register/login/refresh requires auth), blocking calls in async code, missing audit logs on destructive actions. Fix with minimal diffs and list each fix. (2) Add security headers middleware (X-Content-Type-Options, X-Frame-Options DENY, Referrer-Policy) and a request body limit outside uploads. (3) `/ready` checks DB (`SELECT 1`) and Redis ping. (4) `scripts/seed_demo.py`: creates a demo org, admin/manager/employee users with known passwords for the viva. (5) Dockerfile (python:3.12-slim, uv, non-root user, copies `../ai` too — build context is the repo root; document it), entrypoint runs `alembic upgrade head` then uvicorn with `--proxy-headers`. (6) README: env vars table, run locally, run tests, API overview link to /docs, notes for Member 4 (SSE needs `proxy_buffering off` in Nginx; one shared `.env` must include the AI module's MISTRAL/QDRANT variables). Export final `openapi.json`.

**Done when:** `docker build` succeeds from repo root; Member 4 runs the stack with compose; full demo works end to end with real AI.

---

## Part D — Integration checkpoints (put these in the team calendar)
1. **End of week 1:** openapi.json (auth) to Member 1. AI contract confirmed: `ChatMessage.role` allows `system` ✅ and the `done` event carries `usage` ✅ (see Part G).
2. **After Backend Phase 4:** real upload → `ready` → vectors visible in Qdrant.
3. **After Backend Phase 5:** first real streaming chat in the frontend. This is your mid-semester demo.
4. **After Phase 6:** meeting → email chain and report PDF from the UI.
5. **Phase 8:** deployed on cloud by Member 4, demo seeded with `seed_demo.py`.

## Part E — Demo script (backend part)
1. Register org → admin creates a manager and an employee (show temp password + forced change).
2. Manager uploads a manager-only doc; employee can't see it in the list or in chat answers (RBAC end to end).
3. Streaming chat with citations; refresh the page, history is still there (persistence).
4. Meeting transcript → summary → PDF download.
5. Admin dashboard: users, storage, tokens per day, activity log showing everything just done.

## Part F — Common mistakes to avoid
- Forgetting `org_id` in one query → another company's data leaks. The Phase 8 review exists for this; also write the cross-org test in every phase.
- Using the request's DB session after a streaming response starts → "session closed" errors. Save with a new session (Phase 5).
- Storing JWTs in localStorage on the frontend → tell Member 1: access token in memory, refresh via cookie.
- Using `EventSource` on the frontend → it can't POST or send headers; use fetch streaming.
- Nginx buffering SSE → tokens appear all at once. `X-Accel-Buffering: no` + `proxy_buffering off`.
- Editing an applied migration → teammates' DBs break. Always add a new one.
- Calling real Mistral in tests → slow, flaky, burns quota. FakeAIGateway only.
- Returning 403 for other orgs' resources → reveals they exist. Use 404.

---

## Part G — Adjustments from the review against the finished AI module (2026-10-22)

| Phase | Adjustment |
|---|---|
| 0 | `.env.example` also lists the AI module's variables (`MISTRAL_API_KEY`, `QDRANT_URL`, model names…): `eap_ai` reads `.env` from the current directory, i.e. `Backend/.env`. `docker-compose.yml` also runs **Qdrant** (6333/6334) so one `docker compose up -d` starts everything. |
| 2 | Add a guard: while `must_change_password` is true, only `/users/me`, `/users/me/password` and `/auth/*` are allowed (others → 403 `password_change_required`). |
| 2, 5 | Rate limits: keep 30/min per user **and** add an org-wide AI limit. The Mistral smart model allows ~30 req/min for the whole account. The AI module already retries 429s with backoff. |
| 4 | `FakeAIGateway.run` mirrors the real stream exactly: `status` "Planning…" → `agent {name, step, total, instruction}` → `sources` → `token`* → `result {agent, output, …}` → `done {answer, agents, errors, usage}`. `error` events do **not** end the stream; `done` is always last. |
| 4 | Ingest errors: `eap_ai.service.IngestError` subclasses (`FileTooLarge`, `UnsupportedFileType`, `UnreadableDocument`) have user-safe messages → store `str(exc)` as `documents.error`; any other exception → generic message (log the full one). |
| 4, 5, 6 | Usage mapping: AI `done.usage = {input_tokens, output_tokens, total_tokens, by_model}` → `prompt_tokens = input_tokens`, `completion_tokens = output_tokens`. |
| 5 | `ChatMessage.role` accepts `system`. Pass the previous summary as a `system` message to `summarize_history`. |
| 6 | Meeting and report `result` events already include `markdown` (from the AI's `to_markdown()`); use it. `services/markdown.py` only needs **email** and **document insights**. |
| 8 | The AI module has its own `ai/Dockerfile` (uv, non-root, tiktoken prefetched). The backend image builds from the repo root and installs both packages; reuse that pattern. |
| all | AI module contract and env vars: `ai/README.md`. Use `127.0.0.1` instead of `localhost` on Windows (avoids a ~2 s IPv6 delay per request). |
