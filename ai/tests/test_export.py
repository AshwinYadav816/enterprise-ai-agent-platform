from datetime import UTC, datetime

import pymupdf
import pytest

from eap_ai import service
from eap_ai.agents.meeting import ActionItem, MeetingSummary
from eap_ai.agents.report import Report, ReportSection, ReportType
from eap_ai.export.pdf import FONTS_DIR, markdown_to_pdf

A4_POINTS = (595, 842)

MD = """# Q3 Report

Café naïve — ₹1,200 · Ünïcode ✓ · Ελληνικά · Привет

| Owner | Task | Due |
|---|---|---|
| Asha | Release notes | Thursday |
| Unassigned | Book room | — |

- **bold** and *italic* and `code`
"""


def _open(pdf: bytes) -> pymupdf.Document:
    return pymupdf.open(stream=pdf, filetype="pdf")


def _text(pdf: bytes) -> str:
    with _open(pdf) as doc:
        return "\n".join(page.get_text() for page in doc)


def test_pdf_basics_table_and_unicode() -> None:
    pdf = markdown_to_pdf(MD, "Q3 Report — Ünïcode", datetime(2026, 10, 14, 9, 30, tzinfo=UTC))
    assert pdf.startswith(b"%PDF")
    with _open(pdf) as doc:
        assert doc.page_count == 1
        assert tuple(round(x) for x in doc[0].rect[2:]) == A4_POINTS
        assert doc.metadata["title"] == "Q3 Report — Ünïcode"
    text = _text(pdf)
    for expected in ("Café naïve", "₹1,200", "Ünïcode ✓", "Ελληνικά", "Привет"):
        assert expected in text
    for cell in ("Owner", "Asha", "Release notes", "Thursday", "Unassigned"):
        assert cell in text
    assert "Generated 14 Oct 2026 09:30 UTC" in text  # header date
    assert "Page 1 of 1" in text  # footer with total pages


def test_page_numbers_across_pages() -> None:
    pdf = markdown_to_pdf("\n\n".join(f"Paragraph {i}. " * 20 for i in range(60)), "Long")
    with _open(pdf) as doc:
        n = doc.page_count
        assert n > 1
        assert f"Page {n} of {n}" in doc[n - 1].get_text()
        assert all("Long" in page.get_text() for page in doc)  # title header on every page


def test_raw_html_and_images_are_not_rendered() -> None:
    md = (
        '<img src="http://169.254.169.254/x.png"> <script>x</script>\n\n![logo](file:///etc/passwd)'
    )
    pdf = markdown_to_pdf(md, "Untrusted")
    with _open(pdf) as doc:
        assert all(not page.get_images() for page in doc)  # nothing fetched or embedded
    text = _text(pdf)
    assert '<img src="http://169.254.169.254/x.png">' in text  # shown as plain text
    assert "logo" in text and "passwd" not in text


def test_meeting_summary_markdown_exports() -> None:
    summary = MeetingSummary(
        summary="Launch moved to 17 Sept.",
        key_decisions=["Move launch"],
        action_items=[
            ActionItem(task="Update roadmap | page", owner="Rohit", due_date="Friday"),
            ActionItem(task="Tell marketing"),
        ],
        open_questions=["Budget?"],
    )
    md = summary.to_markdown()
    assert "| Update roadmap \\| page | Rohit | Friday |" in md
    assert "| Tell marketing | Unassigned | — |" in md
    text = _text(service.export_pdf(md, "Launch sync"))
    assert "Action items" in text and "Rohit" in text and "Tell marketing" in text


def test_report_markdown_exports() -> None:
    report = Report(
        report_type=ReportType.sprint,
        title="Sprint 7",
        period="1–14 Oct",
        sections=[ReportSection(heading="Progress", content_md="Beta shipped [1].")],
        risks=["Vendor delay"],
    )
    text = _text(service.export_pdf(report.to_markdown(), report.title))
    assert "Sprint 7" in text and "Progress" in text and "Vendor delay" in text


@pytest.mark.parametrize(
    "name",
    ["DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSansMono.ttf", "LICENSE-DejaVu.txt"],
)
def test_fonts_bundled(name: str) -> None:
    assert (FONTS_DIR / name).is_file()


def test_list_directly_after_text_still_renders_as_list() -> None:
    lines = _text(markdown_to_pdf("Revenue:\n- North: 120\n- South: 95", "T")).splitlines()
    assert "Revenue:" in lines
    assert any(line.endswith("North: 120") for line in lines)
    assert any(line.endswith("South: 95") for line in lines)  # separate lines, not merged
