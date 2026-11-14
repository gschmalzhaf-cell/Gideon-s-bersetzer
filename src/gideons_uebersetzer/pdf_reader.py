"""PDF-Textextraktion mit PyMuPDF.

Extrahiert den Text seitenweise, erkennt Kapitel über eine
Schriftgrößen-Heuristik (größere oder fette Zeilen am Absatzanfang beginnen
ein neues Kapitel) und meldet eingescannte PDFs ohne Textebene mit einer
klaren deutschen Fehlermeldung.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

SCANNED_PDF_MESSAGE = (
    "Dieses PDF enthält keine Textebene, sondern nur Bilder. "
    "OCR ist in Version 1 nicht enthalten."
)

_PAGE_NUMBER_RE = re.compile(r"^\s*(?:-?\s*\d{1,4}\s*-?|seite\s+\d{1,4})\s*$", re.IGNORECASE)
_MIN_SPAN_SIZE = 6.0
_BOLD_FLAG = 1 << 4


class PdfError(Exception):
    """Allgemeiner PDF-Fehler mit deutscher, anzeigbarer Meldung."""


class ScannedPdfError(PdfError):
    """Das PDF hat keine Textebene (eingescannt)."""

    def __init__(self, page_number: int):
        self.page_number = page_number
        super().__init__(f"Seite {page_number}: {SCANNED_PDF_MESSAGE}")


@dataclass
class Paragraph:
    text: str
    page: int  # 1-basiert


@dataclass
class Chapter:
    title: str | None
    paragraphs: list[Paragraph] = field(default_factory=list)

    @property
    def word_count(self) -> int:
        return sum(len(p.text.split()) for p in self.paragraphs)


@dataclass
class PdfBook:
    path: Path
    title: str
    author: str
    page_count: int
    chapters: list[Chapter] = field(default_factory=list)

    @property
    def word_count(self) -> int:
        return sum(c.word_count for c in self.chapters)

    @property
    def first_chapter_title(self) -> str | None:
        for chapter in self.chapters:
            if chapter.title:
                return chapter.title
        return None


def _line_info(line: dict) -> tuple[str, float, bool]:
    """Gibt (Text, maximale Schriftgröße, fett) einer Zeile zurück."""
    parts: list[str] = []
    max_size = 0.0
    bold = False
    for span in line.get("spans", []):
        text = span.get("text", "")
        if not text.strip():
            continue
        size = float(span.get("size", 0.0))
        if size < _MIN_SPAN_SIZE:
            continue
        parts.append(text)
        max_size = max(max_size, size)
        if span.get("flags", 0) & _BOLD_FLAG:
            bold = True
    return " ".join("".join(parts).split()), max_size, bold


def _body_size(pages_dicts: list[dict]) -> float:
    """Häufigste Schriftgröße im Dokument = Fließtext-Größe."""
    sizes: Counter[float] = Counter()
    for page in pages_dicts:
        for block in page.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    size = round(float(span.get("size", 0.0)) * 2) / 2
                    if size >= _MIN_SPAN_SIZE:
                        sizes[size] += len(span.get("text", "").strip())
    if not sizes:
        return 11.0
    return sizes.most_common(1)[0][0]


def extract_book(path: str | Path) -> PdfBook:
    """Liest ein PDF ein und liefert ein PdfBook mit Kapiteln und Absätzen.

    Raises:
        ScannedPdfError: wenn eine Seite keinen extrahierbaren Text enthält.
        PdfError: bei sonstigen Leseproblemen.
    """
    path = Path(path)
    if not path.is_file():
        raise PdfError(f"Die Datei wurde nicht gefunden: {path}")
    try:
        doc = pymupdf.open(path)
    except Exception as exc:
        raise PdfError(f"Das PDF konnte nicht geöffnet werden: {path.name} ({exc})") from exc

    with doc:
        if doc.needs_pass:
            raise PdfError("Das PDF ist passwortgeschützt und kann nicht gelesen werden.")
        meta = doc.metadata or {}
        title = (meta.get("title") or "").strip() or path.stem
        author = (meta.get("author") or "").strip() or "Unbekannt"

        pages_dicts = [page.get_text("dict") for page in doc]

        for index, page_dict in enumerate(pages_dicts, start=1):
            has_text = any(
                span.get("text", "").strip()
                for block in page_dict.get("blocks", [])
                for line in block.get("lines", [])
                for span in line.get("spans", [])
            )
            if not has_text:
                raise ScannedPdfError(index)

        body_size = _body_size(pages_dicts)
        chapters: list[Chapter] = []
        current = Chapter(title=None)
        chapters.append(current)

        for page_number, page_dict in enumerate(pages_dicts, start=1):
            for block in page_dict.get("blocks", []):
                if block.get("type", 0) != 0:
                    continue
                block_lines: list[tuple[str, float, bool]] = []
                for line in block.get("lines", []):
                    text, size, bold = _line_info(line)
                    if text:
                        block_lines.append((text, size, bold))
                if not block_lines:
                    continue
                first_text, first_size, first_bold = block_lines[0]
                if _PAGE_NUMBER_RE.match(first_text):
                    continue
                is_heading = (
                    first_size > body_size * 1.15
                    or (first_bold and first_size >= body_size * 1.02 and len(first_text) <= 120)
                ) and len(first_text) <= 160
                if is_heading:
                    current = Chapter(title=first_text)
                    chapters.append(current)
                    rest = " ".join(t for t, _, _ in block_lines[1:])
                    if rest:
                        current.paragraphs.append(Paragraph(rest, page_number))
                else:
                    text = " ".join(t for t, _, _ in block_lines)
                    current.paragraphs.append(Paragraph(text, page_number))

        chapters = [c for c in chapters if c.paragraphs or c.title]
        if not chapters:
            raise PdfError("Im PDF wurde kein Text gefunden.")

        return PdfBook(
            path=path,
            title=title,
            author=author,
            page_count=len(pages_dicts),
            chapters=chapters,
        )


def extract_cover_png(path: str | Path, page_number: int = 1, max_width: int = 600) -> bytes | None:
    """Extrahiert eine Seite als PNG-Bild (für die EPUB-Titelseite), optional."""
    try:
        with pymupdf.open(path) as doc:
            page = doc[page_number - 1]
            zoom = max_width / max(page.rect.width, 1)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
            return pix.tobytes("png")
    except Exception:
        return None
