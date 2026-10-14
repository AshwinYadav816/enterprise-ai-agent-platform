# EAP-AI

AI module of the Enterprise AI Agent Platform: document ingestion, RAG, agents and orchestration.
The backend uses it only through `eap_ai.service` (types in `eap_ai.schemas`).

## Run locally

Prerequisites: Docker Desktop running, [uv](https://docs.astral.sh/uv/) installed, and `.env` created from `.env.example` with your `MISTRAL_API_KEY`.

```bash
docker compose up -d                     # 1. start Qdrant (dashboard: http://localhost:6333/dashboard)
uv sync                                  # 2. install dependencies
uv run uvicorn dev_api:app --reload      # 3. start the dev API (Swagger: http://localhost:8000/docs)
```

The dev API is for local testing only; it has no auth. The user is taken from the headers
`X-User-Id`, `X-Org-Id` and `X-Roles` (comma-separated). Defaults: `dev-user`, `demo-org`, `employee`.

Try it:

```bash
# upload a document visible to the hr and employee roles
curl -F "file=@policy.pdf" -F "allowed_roles=hr,employee" http://localhost:8000/ingest

# ask a question (streams Server-Sent Events: sources -> token... -> done)
curl -N http://localhost:8000/chat -H "Content-Type: application/json" -H "X-Roles: employee" \
  -d '{"query": "How many vacation days do I get?"}'

# delete a document
curl -X DELETE http://localhost:8000/docs/<doc_id>
```

Run tests (offline, no API calls): `uv run pytest -q`
