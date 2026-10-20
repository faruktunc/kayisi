"""Basit blok modelinden PDF üretimi (reportlab).

Uygulama katmanı rapor içeriğini blok listesi olarak kurar; bu modül yalnızca
dizgiden sorumludur. Türkçe karakterler ve alt simgeler (SO₂) için
matplotlib ile gelen DejaVu Sans fontu kullanılır.
"""
import io
import os
from dataclasses import dataclass, field
from datetime import datetime

import matplotlib
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_FONT_DIR = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
pdfmetrics.registerFont(TTFont("DejaVu", os.path.join(_FONT_DIR, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-Bold", os.path.join(_FONT_DIR, "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold")

ACCENT = colors.HexColor("#c8691c")
ACCENT_SOFT = colors.HexColor("#fbeadb")
MUTED = colors.HexColor("#7a7468")
BORDER = colors.HexColor("#e2ddd2")
HEADER_BG = colors.HexColor("#f1eee7")

STYLES = {
    "title": ParagraphStyle("title", fontName="DejaVu-Bold", fontSize=16, leading=20, spaceAfter=2),
    "subtitle": ParagraphStyle("subtitle", fontName="DejaVu", fontSize=9, leading=12, textColor=MUTED, spaceAfter=8),
    "h2": ParagraphStyle("h2", fontName="DejaVu-Bold", fontSize=11.5, leading=15, spaceBefore=10, spaceAfter=4, textColor=ACCENT,
                         keepWithNext=1),
    "p": ParagraphStyle("p", fontName="DejaVu", fontSize=9, leading=12.5, alignment=TA_LEFT, spaceAfter=4),
    # Ardından gelen tabloyla aynı sayfada kalan ara başlık
    "lead": ParagraphStyle("lead", fontName="DejaVu", fontSize=9, leading=12.5, spaceAfter=3, keepWithNext=1),
    "note": ParagraphStyle("note", fontName="DejaVu", fontSize=7.5, leading=10, textColor=MUTED, spaceAfter=4),
    "cell": ParagraphStyle("cell", fontName="DejaVu", fontSize=7.5, leading=9.5),
    "cell_head": ParagraphStyle("cell_head", fontName="DejaVu-Bold", fontSize=7.5, leading=9.5),
    "callout": ParagraphStyle("callout", fontName="DejaVu", fontSize=9.5, leading=13),
}


@dataclass
class TableBlock:
    columns: list[str]
    rows: list[list]
    highlight_rows: set[int] = field(default_factory=set)
    col_widths: list[float] | None = None  # sayfa genişliğinin oranları
    row_height: float | None = None        # mm; elle doldurulacak tablolar için


@dataclass
class Report:
    title: str
    subtitle: str = ""
    landscape: bool = False
    blocks: list = field(default_factory=list)

    def heading(self, text):
        self.blocks.append(("h2", text))

    def paragraph(self, text):
        self.blocks.append(("p", text))

    def lead(self, text):
        self.blocks.append(("lead", text))

    def note(self, text):
        self.blocks.append(("note", text))

    def callout(self, text):
        self.blocks.append(("callout", text))

    def table(self, block: TableBlock):
        self.blocks.append(("table", block))

    def key_values(self, pairs: list[tuple[str, str]], columns: int = 2):
        rows, row = [], []
        for k, v in pairs:
            row += [f"<b>{k}</b>", v]
            if len(row) == 2 * columns:
                rows.append(row)
                row = []
        if row:
            rows.append(row + [""] * (2 * columns - len(row)))
        self.blocks.append(("kv", rows))

    def image(self, png: bytes, width_ratio: float = 1.0):
        self.blocks.append(("image", (png, width_ratio)))

    def page_break(self):
        self.blocks.append(("pagebreak", None))

    def spacer(self, h_mm: float = 4):
        self.blocks.append(("spacer", h_mm))


def _cell(value, head=False):
    if isinstance(value, Paragraph):
        return value
    return Paragraph("" if value is None else str(value), STYLES["cell_head" if head else "cell"])


def render(report: Report) -> bytes:
    buf = io.BytesIO()
    pagesize = landscape(A4) if report.landscape else A4
    margin = 14 * mm
    doc = SimpleDocTemplate(buf, pagesize=pagesize, leftMargin=margin, rightMargin=margin,
                            topMargin=margin, bottomMargin=16 * mm, title=report.title,
                            author="Kayısı proses simülatörü")
    width = pagesize[0] - 2 * margin
    story = [Paragraph(report.title, STYLES["title"])]
    if report.subtitle:
        story.append(Paragraph(report.subtitle, STYLES["subtitle"]))

    for kind, payload in report.blocks:
        if kind in ("h2", "p", "lead", "note"):
            story.append(Paragraph(payload, STYLES[kind]))
        elif kind == "callout":
            t = Table([[Paragraph(payload, STYLES["callout"])]], colWidths=[width])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), ACCENT_SOFT),
                ("LINEBEFORE", (0, 0), (0, -1), 3, ACCENT),
                ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            story += [t, Spacer(1, 4 * mm)]
        elif kind == "kv":
            n_cols = len(payload[0]) if payload else 2
            ratios = [0.22, 0.28] * (n_cols // 2)
            t = Table([[_cell(c) for c in r] for r in payload],
                      colWidths=[width * r / sum(ratios) for r in ratios])
            t.setStyle(TableStyle([
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))
            story += [t, Spacer(1, 3 * mm)]
        elif kind == "table":
            story += [_table(payload, width), Spacer(1, 3 * mm)]
        elif kind == "image":
            png, ratio = payload
            img = Image(io.BytesIO(png))
            scale = width * ratio / img.imageWidth
            img.drawWidth, img.drawHeight = img.imageWidth * scale, img.imageHeight * scale
            story += [KeepTogether([img]), Spacer(1, 3 * mm)]
        elif kind == "pagebreak":
            story.append(PageBreak())
        elif kind == "spacer":
            story.append(Spacer(1, payload * mm))

    stamp = datetime.now().strftime("%d.%m.%Y %H:%M")

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("DejaVu", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(margin, 9 * mm, f"{report.title} · {stamp}")
        canvas.drawRightString(pagesize[0] - margin, 9 * mm, f"Sayfa {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


def _table(block: TableBlock, width: float) -> Table:
    data = [[_cell(c, head=True) for c in block.columns]] + [[_cell(v) for v in row] for row in block.rows]
    if block.col_widths:
        total = sum(block.col_widths)
        widths = [width * w / total for w in block.col_widths]
    else:
        widths = [width / len(block.columns)] * len(block.columns)
    heights = None
    if block.row_height:
        heights = [None] + [block.row_height * mm] * len(block.rows)
    t = Table(data, colWidths=widths, rowHeights=heights, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, MUTED),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]
    if block.row_height:
        style.append(("GRID", (0, 0), (-1, -1), 0.3, BORDER))
    for i in block.highlight_rows:
        style.append(("BACKGROUND", (0, i + 1), (-1, i + 1), ACCENT_SOFT))
    t.setStyle(TableStyle(style))
    return t
