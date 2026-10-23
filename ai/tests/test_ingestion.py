import io
from collections.abc import AsyncIterator

import pymupdf
import pytest
from docx import Document
from openpyxl import Workbook
from pptx import Presentation
from pptx.util import Inches

from eap_ai import llm
from eap_ai.ingestion import pipeline
from eap_ai.ingestion.chunker import chunk_pages
from eap_ai.ingestion.loaders import (
    MAX_XLSX_ROWS,
    Page,
    UnreadableDocument,
    UnsupportedFileType,
    load_document,
)
from eap_ai.schemas import DocMeta
from eap_ai.vectorstore import qdrant
from tests.fakes import FakeEmbedder

# In-memory Qdrant ignores payload indexes; the server honours them.
pytestmark = pytest.mark.filterwarnings("ignore:Payload indexes have no effect")

# --- sample files, generated in memory (no binaries committed) --------------


@pytest.fixture
def pdf_bytes() -> bytes:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Annual leave policy: employees get 24 days per year.")
    doc.new_page()  # blank page -> skipped and flagged
    doc.new_page().insert_text((72, 72), "Remote work requires manager approval in writing.")
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def docx_bytes() -> bytes:
    d = Document()
    d.add_paragraph("Project Phoenix status report.")
    table = d.add_table(rows=2, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "Owner", "Task"
    table.cell(1, 0).text, table.cell(1, 1).text = "Asha", "Deploy API"
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


@pytest.fixture
def pptx_bytes() -> bytes:
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = "Q3 Roadmap"
    box = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(4), Inches(1))
    box.text_frame.text = "Launch mobile app"
    slide.notes_slide.notes_text_frame.text = "Mention budget risk"
    prs.slides.add_slide(prs.slide_layouts[6])  # empty slide -> skipped
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def _xlsx(rows: int) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sales"
    ws.append(["Region", "Revenue"])
    for i in range(rows):
        ws.append([f"R{i}", i * 10])
    wb.create_sheet("Empty")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# --- loaders ------------------------------------------------------------------


def test_pdf_loader_pages_and_scanned_flag(pdf_bytes: bytes) -> None:
    pages, warnings = load_document(pdf_bytes, "policy.PDF")
    assert [p.page_no for p in pages] == [1, 3]
    assert "24 days" in pages[0].text
    assert any("possibly scanned" in w and "[2]" in w for w in warnings)


def test_pdf_loader_expands_ligatures() -> None:
    buf = io.BytesIO()
    writer = pymupdf.DocumentWriter(buf)
    story = pymupdf.Story(html="<p>Staff benefits and office files</p>")  # typeset with ligatures
    device = writer.begin_page(pymupdf.paper_rect("a4"))
    story.place(pymupdf.Rect(50, 50, 500, 500))
    story.draw(device)
    writer.end_page()
    writer.close()
    pages, _ = load_document(buf.getvalue(), "benefits.pdf")
    assert "benefits" in pages[0].text and "files" in pages[0].text
    assert "ﬁ" not in pages[0].text


def test_docx_loader_paragraphs_and_tables(docx_bytes: bytes) -> None:
    pages, _ = load_document(docx_bytes, "report.docx")
    assert len(pages) == 1
    text = pages[0].text
    assert "Project Phoenix" in text
    assert "| Owner | Task |" in text and "| Asha | Deploy API |" in text


def test_pptx_loader_slides_and_notes(pptx_bytes: bytes) -> None:
    pages, _ = load_document(pptx_bytes, "deck.pptx")
    assert len(pages) == 1 and pages[0].page_no == 1
    assert "Q3 Roadmap" in pages[0].text
    assert "Launch mobile app" in pages[0].text
    assert "Notes: Mention budget risk" in pages[0].text


def test_xlsx_loader_markdown_table() -> None:
    pages, warnings = load_document(_xlsx(3), "sales.xlsx")
    assert len(pages) == 1  # empty sheet skipped
    assert pages[0].extra["sheet"] == "Sales"
    assert "| Region | Revenue |" in pages[0].text and "| R2 | 20 |" in pages[0].text
    assert warnings == []


def test_xlsx_loader_caps_rows() -> None:
    pages, warnings = load_document(_xlsx(MAX_XLSX_ROWS + 50), "big.xlsx")
    data_rows = [
        ln for ln in pages[0].text.splitlines() if ln.startswith("| R") and "Region" not in ln
    ]
    assert len(data_rows) == MAX_XLSX_ROWS - 1  # header counts toward the cap
    assert any("truncated" in w for w in warnings)


def test_unsupported_file_type() -> None:
    with pytest.raises(UnsupportedFileType):
        load_document(b"hello", "notes.txt")


# --- chunker ------------------------------------------------------------------


def test_chunks_keep_page_and_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHUNK_SIZE", "50")
    monkeypatch.setenv("CHUNK_OVERLAP", "5")
    long_text = " ".join(f"Sentence number {i} about the travel policy." for i in range(60))
    pages = [Page(long_text, 4, {"label": "p.4"}), Page("Short page.", 5, {"label": "p.5"})]
    chunks = chunk_pages(pages, "handbook.pdf")
    assert len(chunks) > 2
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert all(c.text.startswith("[handbook.pdf — p.4] ") for c in chunks[:-1])
    assert chunks[-1].page == 5 and chunks[-1].text == "[handbook.pdf — p.5] Short page."
    assert len({c.content_hash for c in chunks}) == len(chunks)


def test_chunk_prefix_without_page() -> None:
    (chunk,) = chunk_pages([Page("Body text.", None)], "memo.docx")
    assert chunk.text == "[memo.docx] Body text." and chunk.page is None


# --- ingest + search round trip (in-memory Qdrant, fake embedder) ------------


@pytest.fixture
async def store(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[FakeEmbedder]:
    monkeypatch.setenv("QDRANT_URL", ":memory:")
    fake = FakeEmbedder()
    llm.clear_caches()
    monkeypatch.setattr(llm, "get_embedder", lambda: fake)
    await qdrant.close_client()
    yield fake
    await qdrant.close_client()
    llm.clear_caches()


def _meta(doc_id: str = "d1", org: str = "org1", roles: list[str] | None = None) -> DocMeta:
    return DocMeta(doc_id=doc_id, org_id=org, owner_id="u1", allowed_roles=roles or ["hr"])


async def _count(org: str, roles: list[str]) -> int:
    return len(await qdrant.search([1.0] + [0.0] * 63, org, roles, limit=100))


async def test_ingest_and_search_round_trip(store: FakeEmbedder, pdf_bytes: bytes) -> None:
    result = await pipeline.ingest(pdf_bytes, "policy.pdf", _meta())
    assert result.pages == 2 and result.chunks == 2
    assert any("possibly scanned" in w for w in result.warnings)
    assert await qdrant.collection_name() == "docs_mistral_embed_64"

    hits = await qdrant.search(store.embed_query("annual leave days"), "org1", ["hr"])
    top = hits[0].payload or {}
    assert "24 days" in top["text"] and top["page"] == 1
    assert top["filename"] == "policy.pdf" and top["owner_id"] == "u1"
    assert {"org_id", "doc_id", "allowed_roles", "chunk_index", "content_hash"} <= top.keys()


async def test_search_enforces_org_and_roles(store: FakeEmbedder, pdf_bytes: bytes) -> None:
    await pipeline.ingest(pdf_bytes, "policy.pdf", _meta(roles=["hr", "admin"]))
    assert await _count("org1", ["hr"]) == 2
    assert await _count("org1", ["employee", "admin"]) == 2
    assert await _count("org2", ["hr"]) == 0  # other org
    assert await _count("org1", ["finance"]) == 0  # disallowed role
    assert await _count("org1", []) == 0  # no roles -> nothing


async def test_search_doc_ids_filter(store: FakeEmbedder, pdf_bytes: bytes) -> None:
    await pipeline.ingest(pdf_bytes, "a.pdf", _meta("dA"))
    await pipeline.ingest(pdf_bytes, "b.pdf", _meta("dB"))
    q = store.embed_query("leave policy")
    hits = await qdrant.search(q, "org1", ["hr"], doc_ids=["dB"])
    assert hits and {(h.payload or {})["doc_id"] for h in hits} == {"dB"}


async def test_reingest_overwrites_and_delete(store: FakeEmbedder, pdf_bytes: bytes) -> None:
    await pipeline.ingest(pdf_bytes, "policy.pdf", _meta())
    await pipeline.ingest(pdf_bytes, "policy.pdf", _meta())
    assert await _count("org1", ["hr"]) == 2  # no duplicates

    records = await qdrant.scroll_doc("d1", "org1", ["hr"])
    assert [(r.payload or {})["chunk_index"] for r in records] == [0, 1]
    assert await qdrant.scroll_doc("d1", "org1", ["finance"]) == []

    await qdrant.delete_by_doc("d1", "org2")  # wrong org: no effect
    assert await _count("org1", ["hr"]) == 2
    await qdrant.delete_by_doc("d1", "org1")
    assert await _count("org1", ["hr"]) == 0


async def test_embedding_batches_and_429_backoff(
    store: FakeEmbedder, monkeypatch: pytest.MonkeyPatch, pdf_bytes: bytes
) -> None:
    monkeypatch.setenv("EMBED_BATCH_SIZE", "1")
    sleeps: list[float] = []

    async def fake_sleep(s: float) -> None:
        sleeps.append(s)

    monkeypatch.setattr(pipeline, "_sleep", fake_sleep)
    real = store.aembed_documents
    failures = iter([True, True])

    async def flaky(texts: list[str]) -> list[list[float]]:
        if next(failures, False):
            raise RuntimeError("Error response 429: Rate limit exceeded")
        return await real(texts)

    monkeypatch.setattr(store, "aembed_documents", flaky)
    await llm.embedding_dim()  # warm the one-time dimension probe
    store.calls = 0
    result = await pipeline.ingest(pdf_bytes, "policy.pdf", _meta())
    assert result.chunks == 2
    assert store.calls == 2  # batch size 1 -> one call per chunk
    assert sleeps == [2.0, 4.0]  # exponential backoff


async def test_non_rate_limit_error_is_not_retried(
    store: FakeEmbedder, monkeypatch: pytest.MonkeyPatch, pdf_bytes: bytes
) -> None:
    async def broken(texts: list[str]) -> list[list[float]]:
        raise RuntimeError("401 Unauthorized")

    monkeypatch.setattr(store, "aembed_documents", broken)
    with pytest.raises(RuntimeError, match="401"):
        await pipeline.ingest(pdf_bytes, "policy.pdf", _meta())


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("bad.pdf", b"not a pdf"),
        ("bad.docx", b"junk"),
        ("bad.xlsx", b"junk"),
        ("bad.pptx", b"PK junk"),
    ],
)
def test_corrupt_files_raise_clear_error(name: str, data: bytes) -> None:
    with pytest.raises(UnreadableDocument, match="damaged or not a valid"):
        load_document(data, name)


def test_empty_and_password_protected_files() -> None:
    with pytest.raises(UnreadableDocument, match="empty"):
        load_document(b"", "a.pdf")
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "secret")
    locked = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="o", user_pw="u")
    with pytest.raises(UnreadableDocument, match="password-protected"):
        load_document(locked, "locked.pdf")
