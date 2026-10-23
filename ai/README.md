# EAP-AI

AI module of the Enterprise AI Agent Platform: document ingestion, RAG, five specialised agents
(research, email, meeting, report, document) plus chat, and a LangGraph orchestrator.

The backend uses it **only** through `eap_ai.service`, with types from `eap_ai.schemas`. The module
is stateless: the backend owns users, auth, chat history and file storage.

## Run locally

Prerequisites: Docker Desktop running, [uv](https://docs.astral.sh/uv/) installed, and `.env`
created from `.env.example` with your `MISTRAL_API_KEY`.

```bash
docker compose up -d                     # 1. start Qdrant (dashboard: http://localhost:6333/dashboard)
uv sync                                  # 2. install dependencies
uv run uvicorn dev_api:app --reload      # 3. start the dev API (Swagger: http://localhost:8000/docs)
```

The dev API is for local testing only; it has no auth. The user is taken from the headers
`X-User-Id`, `X-Org-Id` and `X-Roles` (comma-separated). Defaults: `dev-user`, `demo-org`, `employee`.

```bash
# upload a document visible to the hr and employee roles
curl -F "file=@policy.pdf" -F "allowed_roles=hr,employee" http://127.0.0.1:8000/ingest

# ask (Server-Sent Events: status, agent, sources, token..., result, done)
curl -N http://127.0.0.1:8000/chat -H "Content-Type: application/json" -H "X-Roles: employee" \
  -d '{"query": "How many vacation days do I get?"}'

# delete a document
curl -X DELETE http://127.0.0.1:8000/docs/<doc_id>
```

On Windows use `127.0.0.1` rather than `localhost`; `localhost` adds about 2 s per request (IPv6 fallback).

Tests (offline, fake models, no API cost): `uv run pytest -q`.
Evaluation with real models: see [eval/README.md](eval/README.md).

## Service API (for the backend)

```python
from eap_ai import service
from eap_ai.schemas import AgentRequest, ChatMessage, DocMeta, UserCtx
```

| function | purpose |
|---|---|
| `await service.ingest_document(file_bytes, filename, meta: DocMeta) -> IngestResult` | parse, chunk, embed and index; same `doc_id` again **replaces** the document |
| `await service.delete_document(doc_id, org_id) -> None` | remove a document's chunks (scoped to the org) |
| `async for event in service.run(req: AgentRequest)` | route and answer; stream of `Event`, never raises, always ends with `done` |
| `await service.summarize_history(messages) -> str` | rolling summary of older chat turns (≤150 words) |
| `service.export_pdf(markdown, title) -> bytes` | A4 PDF (Unicode, header, page numbers). **Sync**: call with `await asyncio.to_thread(...)` |
| `await service.health() -> dict[str, str]` | `{"config": "ok" or "invalid", "qdrant": "ok" or "unavailable"}` for the backend's readiness probe; never raises, never calls Mistral |

### Inputs
```python
DocMeta(doc_id, org_id, owner_id, allowed_roles: list[str])
UserCtx(user_id, org_id, roles: list[str])
AgentRequest(query, user: UserCtx, history: list[ChatMessage] = [], history_summary: str | None = None,
             force_agent: AgentName | None = None,   # research|email|meeting|report|document|chat
             doc_ids: list[str] | None = None,       # restrict to / analyze these documents
             transcript: str | None = None)          # meeting transcript text
```

### Event stream (forward each event as one SSE `data:` line of JSON)
| type | data | notes |
|---|---|---|
| `status` | `{message}` | "Planning…", "Plan: meeting → email", progress text |
| `agent` | `{name, step, total, instruction}` | a plan step starts |
| `sources` | `{sources: [{n, doc_id, filename, page, snippet}]}` | documents used; the answer cites them as `[n]` |
| `token` | `{text}` | streamed answer text: append to the message |
| `result` | `{agent, output, ...}` | structured output for UI cards (email, meeting summary, report, …). Report and meeting results include `markdown` ready for `export_pdf` |
| `error` | `{message, agent?}` | user-safe message; the stream continues |
| `done` | `{answer, agents, errors, usage}` | always last. `usage = {input_tokens, output_tokens, total_tokens, by_model}` for the admin dashboard |

### Ingest errors
`ingest_document` raises subclasses of `service.IngestError` (a `ValueError`) whose messages are
safe to show the user. Suggested HTTP codes: `FileTooLarge` → 413 (limit `MAX_UPLOAD_MB`, default 25),
`UnsupportedFileType` → 415 (pdf, docx, pptx, xlsx only), `UnreadableDocument` → 422 (empty,
corrupted or password-protected).

### Backend responsibilities
- **Authentication and authorisation.** Build `UserCtx` from the authenticated user. Retrieval always
  filters by `org_id` and `roles`, but `delete_document` only checks the org, so verify the caller
  may delete the document.
- **Chat history.** When a conversation exceeds 12 messages, call
  `summarize_history(history[:-6])` (pass the previous summary as the first message), store it,
  and send `history_summary` + the last 6 messages.
- **Store the original files** if needed; this module keeps only chunks and vectors.

## Configuration

Set as environment variables or in `.env`. Only `MISTRAL_API_KEY` is required.

| variable | default | meaning |
|---|---|---|
| `MISTRAL_API_KEY` | (required) | Mistral API key (only LLM and embedding provider) |
| `FAST_MODEL` | `ministral-8b-latest` | fast tasks: `router`, `rewrite`, `classify`, `summary`, `map`, `judge` |
| `SMART_MODEL` | `ministral-14b-latest` | smart tasks: `answer`, `chat`, `synthesis`, `report`, `meeting`, `email`, `document` |
| `TASK_MODELS` | `{}` | per-task override as JSON, e.g. `{"email": "ministral-8b-latest"}`; unknown task names are rejected at startup |
| `FAST_FALLBACK_MODELS` | `["ministral-3b-latest"]` | tried in order when a fast task's model is busy (429), down (5xx) or times out |
| `SMART_FALLBACK_MODELS` | `["ministral-8b-latest"]` | same for smart tasks; `[]` turns fallback off |
| `EMBEDDING_MODEL` | `mistral-embed` | the collection name includes model and dimension |
| `FAST_REASONING_EFFORT` | `none` | applied only if the installed client supports it |
| `LLM_TIMEOUT` | `60` | seconds per HTTP call |
| `LLM_MAX_RETRIES` | `2` | retries on 429 / 5xx / timeouts |
| `LLM_RETRY_BACKOFF` | `1.0` | seconds; doubles each retry |
| `EMBED_BATCH_SIZE` | `16` | texts per embedding request |
| `MAX_UPLOAD_MB` | `25` | ingest rejects larger files |
| `QDRANT_URL` | `http://localhost:6333` | `:memory:` for an in-process store (tests) |
| `QDRANT_API_KEY` | (empty) | for Qdrant Cloud |
| `REDIS_URL` | (empty) | embedding cache; empty = in-process LRU |
| `CACHE_MAX_ITEMS` | `5000` | in-process cache size (~4 KB per vector) |
| `QUERY_EMBEDDING_TTL` | `3600` | seconds a query embedding stays cached |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `600` / `80` | tokens per chunk / overlap |
| `TOP_K` / `FINAL_K` | `20` / `5` | candidates searched / sources given to the model |
| `SCORE_THRESHOLD` | `0.62` | minimum similarity; below it the answer is "couldn't find" without an LLM call |
| `MMR_LAMBDA` | `0.7` | relevance vs. diversity when picking sources |
| `MAX_CONTEXT_TOKENS` | `6000` | token budget for sources in the prompt |
| `LONG_INPUT_TOKENS` / `MAP_CHUNK_TOKENS` | `6000` / `3000` | transcripts and documents above this use map-reduce |

### Models per task and fallbacks

Every LLM call names its task (`config.TASK_TIERS`); the task picks its model: `TASK_MODELS`
override, else its tier's `FAST_MODEL` / `SMART_MODEL`. When that model answers 429 (rate limit or
"no capacity", Mistral code 3505) the same request goes straight to the next fallback; 5xx and
timeouts are retried `LLM_MAX_RETRIES` times first. A stream switches only before its first token,
so users never see repeated text. Every switch is logged (`<model> unavailable (…); using <model>`)
and token usage is counted for the model that actually answered (admin dashboard).

- Choose fallbacks from models your plan really serves: on the current plan `open-mistral-nemo` is
  served by `ministral-8b`, and `mistral-small` / `medium` / `large` are blocked.
- Smart tasks don't fall back to `ministral-3b` by default: a weaker model writing grounded answers
  is more likely to add unsupported content, and "busy, try again" is the safer failure.
- Embeddings have **no fallback**: stored vectors only match queries embedded by the same model, so
  a second embedding model would mean indexing every document twice. If `mistral-embed` is down,
  chat says "The AI service is busy right now" and uploads retry with backoff.
- Changing a task's model: run `eval/run_eval.py` before and after (README there) and keep the
  change only if the scores hold.

## Docker

```bash
docker build -t eap-ai .
docker run --rm eap-ai                                           # smoke test: prints "eap-ai ready"
docker run --rm --env-file .env -e QDRANT_URL=http://qdrant:6333 eap-ai python your_script.py
```

The image is `python:3.12-slim`, installs the locked production dependencies with uv into `/opt/venv`
(on `PATH`), runs as non-root user `app` (uid 10001), and pre-downloads the tiktoken tokenizer
so containers need no extra downloads at runtime. `.dockerignore` is a whitelist, so `.env` and other
secrets are never copied into the image; pass them at runtime. The backend can build `FROM eap-ai`
and add its own app on top, then `import eap_ai.service`.
