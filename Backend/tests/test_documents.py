import uuid

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Document, Organization, User, UserRole
from app.services import audit
from app.services.ai_gateway import AgentName, AgentRequest, FakeAIGateway, get_ai, user_ctx
from app.services.documents import GENERIC_INGEST_ERROR, process_document
from app.services.storage import LocalStorage, document_key, safe_filename
from tests.factories import make_org, make_user
from tests.fakes import DOCX_BYTES, PDF_BYTES, CrashingAIGateway, FailingAIGateway

API = "/api/v1"
PASSWORD = "correct-horse-battery"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def auth(client: httpx.AsyncClient, user: User) -> dict[str, str]:
    r = await client.post(f"{API}/auth/login", json={"email": user.email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return bearer(r.json()["access_token"])


async def upload(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    name: str = "policy.pdf",
    data: bytes = PDF_BYTES,
    visibility: str = "employee",
) -> httpx.Response:
    return await client.post(
        f"{API}/documents",
        headers=headers,
        files={"file": (name, data, "application/octet-stream")},
        data={"visibility": visibility},
    )


async def team(db: AsyncSession) -> tuple[Organization, dict[UserRole, User]]:
    org = await make_org(db, "Acme")
    users = {
        role: await make_user(db, org, role=role, email=f"{role.value}@acme.com", password=PASSWORD)
        for role in UserRole
    }
    return org, users


# --- upload → processing → ready ----------------------------------------------------------------


async def test_upload_processing_then_ready(
    client: httpx.AsyncClient, db: AsyncSession, fake_ai: FakeAIGateway, storage: LocalStorage
) -> None:
    org, users = await team(db)
    h = await auth(client, users[UserRole.manager])
    r = await upload(client, h, name="../../HR Policy (v2).PDF", visibility="manager")
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "processing" and body["visibility"] == "manager"
    assert body["filename"] == "HR Policy _v2.pdf" and body["content_type"] == "application/pdf"
    assert "storage_key" not in body
    manager_name = users[UserRole.manager].full_name
    assert body["owner_name"] == manager_name  # shown in the documents table

    # the background task has run by the time the response is handled
    detail = (await client.get(f"{API}/documents/{body['id']}", headers=h)).json()
    assert detail["status"] == "ready" and detail["chunk_count"] == 3 and detail["page_count"] == 2
    assert detail["owner_name"] == manager_name
    listed = (await client.get(f"{API}/documents", headers=h)).json()["items"]
    assert [d["owner_name"] for d in listed] == [manager_name]

    (meta,) = fake_ai.ingested
    assert meta.doc_id == body["id"] and meta.org_id == str(org.id)
    assert meta.allowed_roles == ["manager"] and meta.owner_id == str(users[UserRole.manager].id)

    doc = await db.get(Document, uuid.UUID(body["id"]))
    assert doc is not None and doc.storage_key == f"{org.id}/{doc.id}/HR Policy _v2.pdf"
    assert await storage.open(doc.storage_key) == PDF_BYTES

    dl = await client.get(f"{API}/documents/{body['id']}/download", headers=h)
    assert dl.status_code == 200 and dl.content == PDF_BYTES
    assert dl.headers["content-disposition"] == "attachment; filename*=UTF-8''HR%20Policy%20_v2.pdf"
    logged = await db.scalar(select(AuditLog).where(AuditLog.action == audit.DOCUMENT_UPLOADED))
    assert logged is not None and logged.target_id == doc.id


@pytest.mark.parametrize(
    ("name", "data", "code"),
    [
        ("notes.txt", b"hello", "unsupported_file_type"),
        ("archive.zip", DOCX_BYTES, "unsupported_file_type"),
        ("fake.pdf", DOCX_BYTES, "invalid_file"),  # renamed file: wrong signature
        ("empty.docx", b"", "empty_file"),
    ],
)
async def test_rejected_files_are_400(
    client: httpx.AsyncClient, db: AsyncSession, name: str, data: bytes, code: str
) -> None:
    _, users = await team(db)
    r = await upload(client, await auth(client, users[UserRole.employee]), name=name, data=data)
    assert r.status_code == 400 and r.json()["error"]["code"] == code
    assert await db.scalar(select(Document.id)) is None


async def test_too_large_is_413(
    client: httpx.AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    _, users = await team(db)
    h = await auth(client, users[UserRole.employee])
    big = PDF_BYTES + b"x" * (2**20)
    r = await upload(client, h, data=big)
    assert r.status_code == 413 and r.json()["error"]["code"] == "file_too_large"
    ok = await upload(client, h, data=big[: 2**20])  # exactly at the limit is fine
    assert ok.status_code == 202


async def test_cannot_upload_above_own_role(client: httpx.AsyncClient, db: AsyncSession) -> None:
    _, users = await team(db)
    h = await auth(client, users[UserRole.employee])
    r = await upload(client, h, visibility="manager")
    assert r.status_code == 400 and r.json()["error"]["code"] == "visibility_not_allowed"


# --- visibility ----------------------------------------------------------------


async def test_role_visibility(client: httpx.AsyncClient, db: AsyncSession) -> None:
    _, users = await team(db)
    hm = await auth(client, users[UserRole.manager])
    managers_only = (
        await upload(client, hm, name="budget.xlsx", data=DOCX_BYTES, visibility="manager")
    ).json()
    for_everyone = (await upload(client, hm, name="handbook.pdf")).json()

    he = await auth(client, users[UserRole.employee])
    listed = (await client.get(f"{API}/documents", headers=he)).json()["items"]
    assert [d["id"] for d in listed] == [for_everyone["id"]]
    for path in ("", "/download"):
        r = await client.get(f"{API}/documents/{managers_only['id']}{path}", headers=he)
        assert r.status_code == 404  # not 403: the employee can't learn it exists

    ha = await auth(client, users[UserRole.admin])
    seen = {d["id"] for d in (await client.get(f"{API}/documents", headers=ha)).json()["items"]}
    assert seen == {managers_only["id"], for_everyone["id"]}
    assert (
        await client.get(f"{API}/documents/{managers_only['id']}", headers=ha)
    ).status_code == 200


async def test_other_org_is_404(client: httpx.AsyncClient, db: AsyncSession) -> None:
    _, users = await team(db)
    doc = (await upload(client, await auth(client, users[UserRole.admin]))).json()
    outsider = await make_user(
        db, await make_org(db, "Globex"), role=UserRole.admin, password=PASSWORD
    )
    ho = await auth(client, outsider)
    assert (await client.get(f"{API}/documents", headers=ho)).json()["items"] == []
    for method, path in (("GET", ""), ("GET", "/download"), ("DELETE", "")):
        r = await client.request(method, f"{API}/documents/{doc['id']}{path}", headers=ho)
        assert r.status_code == 404


async def test_list_filters_and_pagination(client: httpx.AsyncClient, db: AsyncSession) -> None:
    _, users = await team(db)
    h = await auth(client, users[UserRole.employee])
    for name in ("q1_report.pdf", "q2_report.pdf", "holiday_list.pdf"):
        await upload(client, h, name=name)

    async def names(**params: str) -> list[str]:
        r = await client.get(f"{API}/documents", headers=h, params=params)
        return [d["filename"] for d in r.json()["items"]]

    assert await names(search="REPORT") == ["q2_report.pdf", "q1_report.pdf"]  # newest first
    assert await names(search="_list") == ["holiday_list.pdf"]  # _ is literal
    assert len(await names(status="ready")) == 3 and await names(status="failed") == []
    first = (await client.get(f"{API}/documents", headers=h, params={"limit": "2"})).json()
    rest = await names(limit="2", cursor=first["next_cursor"])
    assert len(first["items"]) == 2 and len(rest) == 1


# --- delete ----------------------------------------------------------------


async def test_delete_permissions_and_cleanup(
    client: httpx.AsyncClient, db: AsyncSession, fake_ai: FakeAIGateway, storage: LocalStorage
) -> None:
    org, users = await team(db)
    hm = await auth(client, users[UserRole.manager])
    doc = (await upload(client, hm)).json()  # visible to everyone, owned by the manager
    key = document_key(org.id, uuid.UUID(doc["id"]), doc["filename"])

    he = await auth(client, users[UserRole.employee])
    r = await client.delete(f"{API}/documents/{doc['id']}", headers=he)
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"

    assert (await client.delete(f"{API}/documents/{doc['id']}", headers=hm)).status_code == 204
    assert fake_ai.deleted == [(doc["id"], str(org.id))]
    assert (await client.get(f"{API}/documents/{doc['id']}", headers=hm)).status_code == 404
    with pytest.raises(FileNotFoundError):
        await storage.open(key)
    assert await db.scalar(select(AuditLog.id).where(AuditLog.action == audit.DOCUMENT_DELETED))

    other = (await upload(client, he)).json()  # employee's doc: admin may delete it
    ha = await auth(client, users[UserRole.admin])
    assert (await client.delete(f"{API}/documents/{other['id']}", headers=ha)).status_code == 204


# --- failed ingestion ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("gateway", "message"),
    [
        (FailingAIGateway("This PDF is password-protected."), "This PDF is password-protected."),
        (CrashingAIGateway(), GENERIC_INGEST_ERROR),  # internals never reach the user
    ],
)
async def test_failed_ingest_sets_failed(
    app: FastAPI, client: httpx.AsyncClient, db: AsyncSession, gateway: FakeAIGateway, message: str
) -> None:
    app.dependency_overrides[get_ai] = lambda: gateway
    _, users = await team(db)
    h = await auth(client, users[UserRole.employee])
    doc = (await upload(client, h)).json()
    detail = (await client.get(f"{API}/documents/{doc['id']}", headers=h)).json()
    assert detail["status"] == "failed" and detail["error"] == message
    assert detail["chunk_count"] is None


async def test_vectors_removed_if_deleted_during_ingest(
    db: AsyncSession, storage: LocalStorage
) -> None:
    user = await make_user(db)
    doc = Document(
        org_id=user.org_id,
        owner_id=user.id,
        filename="a.pdf",
        content_type="application/pdf",
        size_bytes=len(PDF_BYTES),
        storage_key=f"{user.org_id}/x/a.pdf",
        allowed_roles=["employee"],
    )
    db.add(doc)
    await db.flush()
    await storage.save(doc.storage_key, PDF_BYTES)

    class DeletedMidway(FakeAIGateway):
        async def ingest_document(self, file_bytes, filename, meta):  # type: ignore[no-untyped-def]
            await db.delete(doc)  # the user deletes it while we're embedding
            return await super().ingest_document(file_bytes, filename, meta)

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def session_factory():  # type: ignore[no-untyped-def]
        yield db

    ai = DeletedMidway()
    await process_document(doc.id, session_factory, ai, storage)
    assert ai.deleted == [(str(doc.id), str(user.org_id))]  # orphan vectors cleaned up


# --- helpers ----------------------------------------------------------------


def test_safe_filename() -> None:
    assert safe_filename("../../etc/passwd") == "passwd"
    assert safe_filename("C:\\Users\\me\\Report Q1.DOCX") == "Report Q1.docx"
    assert safe_filename("..hidden.pdf") == "hidden.pdf"
    assert safe_filename("名前.pdf") == "file.pdf"
    assert len(safe_filename("a" * 400 + ".pdf")) == 150


async def test_local_storage_refuses_unsafe_keys(storage: LocalStorage) -> None:
    for key in ("../escape.txt", "a/../../b", "/abs/path", "a\\b", ""):
        with pytest.raises(ValueError):
            await storage.save(key, b"x")
    await storage.save("org/doc/ok.pdf", b"data")
    assert await storage.open("org/doc/ok.pdf") == b"data"
    await storage.delete("org/doc/ok.pdf")
    await storage.delete("org/doc/ok.pdf")  # idempotent


async def test_user_ctx_and_fake_stream_shape(db: AsyncSession) -> None:
    manager = await make_user(db, role=UserRole.manager)
    ctx = user_ctx(manager)
    assert ctx.roles == ["employee", "manager"] and ctx.org_id == str(manager.org_id)

    events = [e async for e in FakeAIGateway().run(AgentRequest(query="hi", user=ctx))]
    assert [e.type for e in events[:4]] == ["status", "status", "agent", "sources"]
    assert events[-2].type == "result" and events[-1].type == "done"
    assert set(events[-1].data) == {"answer", "agents", "errors", "usage"}
    forced = [
        e
        async for e in FakeAIGateway().run(
            AgentRequest(query="x", user=ctx, force_agent=AgentName.meeting)
        )
    ]
    assert forced[-2].data["agent"] == "meeting" and "markdown" in forced[-2].data
