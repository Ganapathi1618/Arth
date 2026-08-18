"""Extract text blocks with geometry, then rebuild the PDF in place.

Strategy: we never generate a new document. We open the original, cover each
text block with an opaque patch, and write the translated text back into the
exact same rectangle. Images, vector diagrams, table rules and page geometry
are untouched because we never remove them.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pymupdf

from app.core.config import LANGUAGES, font_path

MIN_FONT = 5.0
SKIP_CHARS = set("•·—–-—0123456789 \t\n")


@dataclass
class Block:
    page: int
    bbox: tuple[float, float, float, float]
    text: str
    size: float
    bold: bool
    color: int
    align: int
    in_table: bool = False
    translated: str = ""


@dataclass
class DocInfo:
    pages: int
    has_text_layer: bool
    scanned_pages: list[int] = field(default_factory=list)
    multi_column_pages: list[int] = field(default_factory=list)


def inspect(path: str) -> DocInfo:
    """Cheap pre-flight so the UI can warn before the user commits."""
    doc = pymupdf.open(path)
    info = DocInfo(pages=doc.page_count, has_text_layer=False)

    for i, page in enumerate(doc):
        text = page.get_text().strip()
        if len(text) > 40:
            info.has_text_layer = True
        else:
            info.scanned_pages.append(i)

        blocks = [b for b in page.get_text("blocks") if b[6] == 0]
        if _detect_columns(blocks, page.rect.width):
            info.multi_column_pages.append(i)

    doc.close()
    return info


def _detect_columns(blocks: list, page_width: float) -> bool:
    """Two clusters of left-edges on opposite halves means two columns."""
    if len(blocks) < 6:
        return False
    mid = page_width / 2
    left = sum(1 for b in blocks if b[2] < mid * 1.1)
    right = sum(1 for b in blocks if b[0] > mid * 0.9)
    return left >= 3 and right >= 3


def _table_cells(page) -> list[pymupdf.Rect]:
    """Cell rectangles for every table on the page.

    Without this, get_text() merges a whole table row into one block and the
    translated text spills across column rules. Cells must be translated and
    placed individually.
    """
    cells: list[pymupdf.Rect] = []
    try:
        for table in page.find_tables():
            for cell in table.cells:
                if cell:
                    cells.append(pymupdf.Rect(cell))
    except Exception:
        pass
    return cells


def _cell_blocks(page, pno: int, cells: list[pymupdf.Rect]) -> list[Block]:
    out: list[Block] = []
    for rect in cells:
        clip = pymupdf.Rect(rect.x0 + 1, rect.y0 + 1, rect.x1 - 1, rect.y1 - 1)
        if clip.is_empty:
            continue
        data = page.get_text("dict", clip=clip)
        parts, sizes, flags, colors = [], [], [], []
        for blk in data["blocks"]:
            if blk["type"] != 0:
                continue
            for line in blk["lines"]:
                for s in line["spans"]:
                    if s["text"].strip():
                        parts.append(s["text"])
                        sizes.append(s["size"])
                        flags.append(s["flags"])
                        colors.append(s["color"])

        text = " ".join(" ".join(parts).split())
        if not text or all(c in SKIP_CHARS for c in text):
            continue

        out.append(
            Block(
                page=pno,
                bbox=(clip.x0, clip.y0, clip.x1, clip.y1),
                text=text,
                size=round(sorted(sizes)[len(sizes) // 2], 1) if sizes else 9.0,
                bold=sum(1 for f in flags if f & 16) > len(flags) / 2,
                color=max(set(colors), key=colors.count) if colors else 0,
                align=0,
                in_table=True,
            )
        )
    return out


def extract(path: str) -> list[Block]:
    doc = pymupdf.open(path)
    out: list[Block] = []

    for pno, page in enumerate(doc):
        cells = _table_cells(page)
        out.extend(_cell_blocks(page, pno, cells))

        data = page.get_text("dict")
        for blk in data["blocks"]:
            if blk["type"] != 0:
                continue  # image block, leave alone

            # Skip anything already captured as a table cell.
            bb = pymupdf.Rect(blk["bbox"])
            covered = sum((bb & c).get_area() for c in cells if bb.intersects(c))
            if bb.get_area() > 0 and covered > bb.get_area() * 0.45:
                continue

            lines, sizes, flags, colors, x0s = [], [], [], [], []
            for line in blk["lines"]:
                spans = [s for s in line["spans"] if s["text"].strip()]
                if not spans:
                    continue
                lines.append("".join(s["text"] for s in line["spans"]))
                x0s.append(line["bbox"][0])
                for s in spans:
                    sizes.append(s["size"])
                    flags.append(s["flags"])
                    colors.append(s["color"])

            text = " ".join(" ".join(lines).split())
            if not text or all(c in SKIP_CHARS for c in text):
                continue

            size = sorted(sizes)[len(sizes) // 2] if sizes else 11.0
            bold = sum(1 for f in flags if f & 16) > len(flags) / 2
            color = max(set(colors), key=colors.count) if colors else 0

            out.append(
                Block(
                    page=pno,
                    bbox=tuple(blk["bbox"]),
                    text=text,
                    size=round(size, 1),
                    bold=bold,
                    color=color,
                    align=_alignment(x0s, blk["bbox"], data["width"]),
                )
            )

    doc.close()
    return out


def _alignment(x0s: list[float], bbox: tuple, page_width: float) -> int:
    """0 left, 1 center, 2 right - matched to CSS text-align."""
    if len(x0s) < 2:
        block_center = (bbox[0] + bbox[2]) / 2
        if abs(block_center - page_width / 2) < page_width * 0.06:
            return 1
        return 0
    spread = max(x0s) - min(x0s)
    return 1 if spread > 8 else 0


def _css(lang: str) -> tuple[str, pymupdf.Archive]:
    fp = font_path(lang)
    css = f'@font-face {{font-family: body; src: url({fp.name});}}'
    return css, pymupdf.Archive(str(fp.parent))


def rebuild(src_path: str, out_path: str, blocks: list[Block], tgt_lang: str) -> dict:
    """Write translated text back into original geometry.

    Returns per-page stats including any block that had to be shrunk below
    readable size - those are surfaced to the user rather than hidden.
    """
    doc = pymupdf.open(src_path)
    css, archive = _css(tgt_lang)
    align_css = {0: "left", 1: "center", 2: "right"}

    overflow: list[int] = []
    by_page: dict[int, list[Block]] = {}
    for b in blocks:
        by_page.setdefault(b.page, []).append(b)

    for pno, page_blocks in by_page.items():
        page = doc[pno]

        # Cover original text. Redaction removes the underlying glyphs so
        # extraction of the output returns the translation, not the source.
        for b in page_blocks:
            page.add_redact_annot(pymupdf.Rect(b.bbox))
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)

        for b in page_blocks:
            text = b.translated or b.text
            rect = pymupdf.Rect(b.bbox)
            if not b.in_table:
                # Breathing room: translated Indic text is taller per line.
                # Table cells must never grow or they cross column rules.
                rect = pymupdf.Rect(rect.x0, rect.y0 - 1, rect.x1 + 2, rect.y1 + 3)
            hexcol = f"#{b.color:06x}"
            weight = "500" if b.bold else "400"

            size = b.size
            placed = False
            while size >= MIN_FONT:
                html = (
                    f'<div style="font-family:body;font-size:{size:.1f}px;'
                    f"color:{hexcol};font-weight:{weight};"
                    f"text-align:{align_css[b.align]};line-height:{1.15 if b.in_table else 1.25};"
                    f'margin:0">{_escape(text)}</div>'
                )
                spare = page.insert_htmlbox(rect, html, css=css, archive=archive)
                if spare[1] >= 0:
                    placed = True
                    break
                size -= 0.5

            if not placed:
                overflow.append(pno)
                html = (
                    f'<div style="font-family:body;font-size:{MIN_FONT}px;'
                    f'color:{hexcol};margin:0">{_escape(text)}</div>'
                )
                page.insert_htmlbox(rect, html, css=css, archive=archive, scale_low=0.4)

    doc.subset_fonts()
    doc.save(out_path, garbage=3, deflate=True)
    doc.close()

    return {"overflow_pages": sorted(set(overflow))}


def _escape(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
