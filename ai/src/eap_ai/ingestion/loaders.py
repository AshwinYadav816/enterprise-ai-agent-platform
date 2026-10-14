"""File parsers: bytes -> list[Page]. Blocking; callers run them in a thread."""

import io
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import PurePath
from typing import Any

import pymupdf
from docx import Document as DocxDocument
from docx.table import Table as DocxTable
from openpyxl import load_workbook
from pptx import Presentation

MAX_XLSX_ROWS = 2000
SCANNED_CHARS_PER_PAGE = 20


class UnsupportedFileType(ValueError):
    pass


@dataclass(frozen=True)
class Page:
    text: str
    page_no: int | None
    extra: dict[str, Any] = field(default_factory=dict)


Loader = Callable[[bytes, list[str]], list[Page]]


def _md_table(rows: Iterable[Sequence[Any]]) -> str:
    """Rows -> markdown table; first row is the header."""
    lines: list[str] = []
    for i, row in enumerate(rows):
        cells = ["" if c is None else str(c).replace("|", "\\|").replace("\n", " ") for c in row]
        lines.append("| " + " | ".join(cells) + " |")
        if i == 0:
            lines.append("|" + "---|" * len(cells))
    return "\n".join(lines)


def load_pdf(data: bytes, warnings: list[str]) -> list[Page]:
    pages: list[Page] = []
    low_text: list[int] = []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for i, pg in enumerate(doc, start=1):
            text = pg.get_text().strip()
            if len(text) < SCANNED_CHARS_PER_PAGE:
                low_text.append(i)
            if text:
                pages.append(Page(text, i, {"label": f"p.{i}"}))
        total = doc.page_count
    if low_text:
        scope = "all pages" if len(low_text) == total else f"pages {low_text}"
        warnings.append(f"PDF possibly scanned: {scope} have little or no extractable text")
    return pages


def load_docx(data: bytes, warnings: list[str]) -> list[Page]:
    doc = DocxDocument(io.BytesIO(data))
    parts: list[str] = []
    for block in doc.iter_inner_content():
        if isinstance(block, DocxTable):
            rows = [[cell.text.strip() for cell in row.cells] for row in block.rows]
            if any(any(r) for r in rows):
                parts.append(_md_table(rows))
        elif text := block.text.strip():
            parts.append(text)
    text = "\n\n".join(parts)
    return [Page(text, None)] if text else []


def load_pptx(data: bytes, warnings: list[str]) -> list[Page]:
    prs = Presentation(io.BytesIO(data))
    pages: list[Page] = []
    for i, slide in enumerate(prs.slides, start=1):
        parts: list[str] = []
        for shape in slide.shapes:
            if shape.has_text_frame and (t := shape.text_frame.text.strip()):
                parts.append(t)
            elif getattr(shape, "has_table", False) and shape.has_table:
                rows = [[c.text.strip() for c in row.cells] for row in shape.table.rows]
                parts.append(_md_table(rows))
        if slide.has_notes_slide and (notes := slide.notes_slide.notes_text_frame.text.strip()):
            parts.append(f"Notes: {notes}")
        if text := "\n".join(parts):
            pages.append(Page(text, i, {"label": f"slide {i}"}))
    return pages


def load_xlsx(data: bytes, warnings: list[str]) -> list[Page]:
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    pages: list[Page] = []
    try:
        for i, ws in enumerate(wb.worksheets, start=1):
            rows: list[tuple[Any, ...]] = []
            truncated = False
            for row in ws.iter_rows(values_only=True):
                if all(c is None or str(c).strip() == "" for c in row):
                    continue
                if len(rows) >= MAX_XLSX_ROWS:
                    truncated = True
                    break
                rows.append(row)
            if truncated:
                warnings.append(f"Sheet '{ws.title}' truncated to {MAX_XLSX_ROWS} rows")
            if rows:
                text = f"Sheet: {ws.title}\n" + _md_table(rows)
                pages.append(Page(text, i, {"label": f"sheet {ws.title}", "sheet": ws.title}))
    finally:
        wb.close()
    return pages


LOADERS: dict[str, Loader] = {
    ".pdf": load_pdf,
    ".docx": load_docx,
    ".pptx": load_pptx,
    ".xlsx": load_xlsx,
}


def load_document(data: bytes, filename: str) -> tuple[list[Page], list[str]]:
    """Dispatch by extension. Returns non-empty pages and any warnings."""
    ext = PurePath(filename).suffix.lower()
    loader = LOADERS.get(ext)
    if loader is None:
        raise UnsupportedFileType(f"Unsupported file type: {ext or filename}")
    warnings: list[str] = []
    return loader(data, warnings), warnings
