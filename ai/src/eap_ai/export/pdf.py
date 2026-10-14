"""Markdown -> HTML -> PDF (fpdf2). A4, title header, generated date, page numbers, Unicode."""

import html
import re
from datetime import UTC, datetime
from pathlib import Path

import markdown
from fpdf import FPDF
from fpdf.fonts import FontFace, TextStyle

FONTS_DIR = Path(__file__).parent / "fonts"
FONT = "dejavu"
MONO = "dejavumono"
MARGIN_MM = 18
HEADING_RGB = (30, 41, 59)  # dark slate

_IMG_TAG = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_ALT = re.compile(r'\balt="([^"]*)"', re.IGNORECASE)
_BETWEEN_TAGS = re.compile(r">\s*\n\s*<")
_CELL_TAG = re.compile(r"<(td|th)>")
# Markdown needs a blank line before a list that follows a text line; LLMs often omit it.
_LIST_ITEM = r"[ \t]*(?:[-*+]|\d+\.)[ \t]"
_LIST_AFTER_TEXT = re.compile(rf"^((?!{_LIST_ITEM}).*\S.*)\n({_LIST_ITEM})", re.MULTILINE)


class _ReportPDF(FPDF):
    def __init__(self, title: str, generated: str) -> None:
        super().__init__(orientation="portrait", unit="mm", format="A4")
        self.doc_title = title
        self.generated = generated
        self.set_margins(MARGIN_MM, MARGIN_MM + 4, MARGIN_MM)
        self.set_auto_page_break(auto=True, margin=MARGIN_MM)
        self.set_title(title)
        self.set_creator("EAP-AI")
        self.add_font(FONT, "", FONTS_DIR / "DejaVuSans.ttf")
        self.add_font(FONT, "B", FONTS_DIR / "DejaVuSans-Bold.ttf")
        self.add_font(FONT, "I", FONTS_DIR / "DejaVuSans-Oblique.ttf")
        self.add_font(FONT, "BI", FONTS_DIR / "DejaVuSans-BoldOblique.ttf")
        self.add_font(MONO, "", FONTS_DIR / "DejaVuSansMono.ttf")
        self.add_font(MONO, "B", FONTS_DIR / "DejaVuSansMono-Bold.ttf")

    def header(self) -> None:
        self.set_y(10)
        self.set_font(FONT, "B", 9)
        self.set_text_color(90, 90, 90)
        width = self.epw * 0.7
        self.cell(width, 5, self.doc_title[:90], new_x="RIGHT", new_y="TOP")
        self.set_font(FONT, "", 8)
        self.cell(self.epw - width, 5, f"Generated {self.generated}", align="R")
        self.set_draw_color(200, 200, 200)
        self.line(self.l_margin, 16, self.w - self.r_margin, 16)
        self.set_text_color(0, 0, 0)
        self.set_y(MARGIN_MM + 4)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font(FONT, "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5, f"Page {self.page_no()} of {{nb}}", align="C")


def _to_html(markdown_text: str) -> str:
    # Raw HTML in LLM output is shown as text, never interpreted; images are dropped so the
    # renderer can't be made to fetch URLs or read local files.
    escaped = _LIST_AFTER_TEXT.sub(r"\1\n\n\2", html.escape(markdown_text, quote=False))
    body = markdown.markdown(escaped, extensions=["tables", "sane_lists"])
    body = _IMG_TAG.sub(_image_alt, body)
    body = _BETWEEN_TAGS.sub("><", body)  # newlines between blocks render as blank lines
    return _CELL_TAG.sub(r'<\1 align="left">', body)  # default justify stretches cell text


def _image_alt(match: re.Match[str]) -> str:
    alt = _ALT.search(match.group(0))
    return alt.group(1) if alt else ""  # already HTML-escaped by markdown


def markdown_to_pdf(markdown_text: str, title: str, generated_at: datetime | None = None) -> bytes:
    generated = (generated_at or datetime.now(UTC)).strftime("%d %b %Y %H:%M UTC")
    pdf = _ReportPDF(title or "Report", generated)
    pdf.add_page()
    pdf.set_font(FONT, "", 11)
    pdf.write_html(
        _to_html(markdown_text),
        font_family=FONT,
        table_line_separators=True,
        tag_styles={
            "h1": TextStyle(font_style="B", font_size_pt=19, color=HEADING_RGB, b_margin=0.4),
            "h2": TextStyle(
                font_style="B", font_size_pt=14, color=HEADING_RGB, t_margin=5, b_margin=0.35
            ),
            "h3": TextStyle(
                font_style="B", font_size_pt=12, color=HEADING_RGB, t_margin=4, b_margin=0.3
            ),
            "code": FontFace(family=MONO),
            "pre": TextStyle(font_family=MONO, t_margin=4),
        },
    )
    return bytes(pdf.output())
