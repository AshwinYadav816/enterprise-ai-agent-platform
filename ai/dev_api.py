"""Local test API for the AI module. NOT for production: the backend owns auth and routing.

The user comes from headers (no auth): X-User-Id, X-Org-Id, X-Roles (comma-separated).
Run: uv run uvicorn dev_api:app --reload   then open http://localhost:8000/docs
"""

import json
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from eap_ai import service
from eap_ai.schemas import AgentName, AgentRequest, ChatMessage, DocMeta, IngestResult, UserCtx
from eap_ai.service import FileTooLarge, IngestError, UnsupportedFileType

app = FastAPI(title="EAP-AI dev API", version="0.1.0")


def _split(csv: str) -> list[str]:
    return [p.strip() for p in csv.split(",") if p.strip()]


def current_user(
    x_user_id: Annotated[str, Header()] = "dev-user",
    x_org_id: Annotated[str, Header()] = "demo-org",
    x_roles: Annotated[str, Header()] = "employee",
) -> UserCtx:
    return UserCtx(user_id=x_user_id, org_id=x_org_id, roles=_split(x_roles))


User = Annotated[UserCtx, Depends(current_user)]


class ChatBody(BaseModel):
    query: str
    history: list[ChatMessage] = Field(default_factory=list)
    history_summary: str | None = None
    force_agent: AgentName | None = None
    doc_ids: list[str] | None = None
    transcript: str | None = None


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest")
async def ingest(
    file: Annotated[UploadFile, File()],
    allowed_roles: Annotated[str, Form(description="Comma-separated, e.g. hr,employee")],
    user: User,
    doc_id: Annotated[str | None, Form()] = None,
) -> dict[str, object]:
    roles = _split(allowed_roles)
    if not roles:
        raise HTTPException(422, "allowed_roles must contain at least one role")
    meta = DocMeta(
        doc_id=doc_id or str(uuid.uuid4()),
        org_id=user.org_id,
        owner_id=user.user_id,
        allowed_roles=roles,
    )
    try:
        result: IngestResult = await service.ingest_document(
            await file.read(), file.filename or "upload", meta
        )
    except IngestError as exc:
        code = (
            413
            if isinstance(exc, FileTooLarge)
            else 415
            if isinstance(exc, UnsupportedFileType)
            else 422
        )
        raise HTTPException(code, str(exc)) from exc
    return {"doc_id": meta.doc_id, **result.model_dump()}


@app.delete("/docs/{doc_id}", status_code=204)
async def delete_doc(doc_id: str, user: User) -> None:
    await service.delete_document(doc_id, user.org_id)


@app.post("/chat")
async def chat(body: ChatBody, user: User) -> StreamingResponse:
    req = AgentRequest(user=user, **body.model_dump())

    async def sse() -> AsyncIterator[str]:
        async for event in service.run(req):
            yield f"data: {json.dumps(event.model_dump(), ensure_ascii=False)}\n\n"

    return StreamingResponse(
        sse(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
