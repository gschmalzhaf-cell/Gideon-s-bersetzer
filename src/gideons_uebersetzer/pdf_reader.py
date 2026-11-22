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
    "OCR ist ausgeschaltet – bitte in den Einstellungen „OCR für gescannte PDFs“ aktivieren."
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


def _page_has_text(page_dict: dict) -> bool:
    return any(
        span.get("text", "").strip()
        for block in page_dict.get("blocks", [])
        for line in block.get("lines", [])
        for span in line.get("spans", [])
    )


def _ocr_heading(text: str, prev_y: float | None, y: float, height: float) -> bool:
    """Heuristik für Kapitelüberschriften in OCR-Text: kurze Zeile ohne Satzzeichen
    (Fließtext-Zeilen werden durch den Zeilenumbruch oft abgeschnitten und sind
    deutlich länger als echte Überschriften)."""
    if len(text) > 60 or text[-1:] in ".!?,;:\"')“»":
        return False
    if prev_y is not None and y - prev_y > height * 2.0:
        return True
    return prev_y is None  # erste Zeile der Seite


def _normalize_margin_text(text: str) -> str:
    """Normalisiert potenzielle Kopf-/Fußzeilen (Ziffern vereinheitlichen, Kleinschreibung)."""
    return re.sub(r"\d+", "#", " ".join(text.split())).strip().lower()


def _detect_running_headers_footers(pages_dicts: list[dict]) -> set[str]:
    """Erkennt wiederkehrende Kopf- und Fußzeilen (Kolumnentitel) über mehrere Seiten.

    Ein Text gilt als wiederkehrende Kopf-/Fußzeile, wenn er (nach Ziffern-Normalisierung)
    auf mindestens 3 Seiten und mindestens 30 % der Textseiten im ersten oder letzten
    Textblock der Seite vorkommt und höchstens 90 Zeichen lang ist.
    """
    text_pages = [d for d in pages_dicts if _page_has_text(d)]
    if len(text_pages) < 3:
        return set()
    counts: Counter[str] = Counter()
    for page in text_pages:
        text_blocks: list[str] = []
        for block in page.get("blocks", []):
            if block.get("type", 0) != 0:
                continue
            lines = [_line_info(line)[0] for line in block.get("lines", [])]
            lines = [t for t in lines if t]
            if lines:
                text_blocks.append(" ".join(lines))
        if not text_blocks:
            continue
        candidates = {text_blocks[0], text_blocks[-1]}
        seen_on_page: set[str] = set()
        for cand in candidates:
            if len(cand) > 90 or _PAGE_NUMBER_RE.match(cand):
                continue
            norm = _normalize_margin_text(cand)
            if norm and norm not in seen_on_page:
                counts[norm] += 1
                seen_on_page.add(norm)
    threshold = max(3, int(len(text_pages) * 0.3 + 0.999))
    return {norm for norm, c in counts.items() if c >= threshold}


def _join_lines(lines: list[str]) -> str:
    """Fügt PDF-Zeilen zu einem Absatz zusammen und heilt Silbentrennungen am Zeilenende."""
    if not lines:
        return ""
    out = lines[0].replace("\xad", "")
    for nxt in lines[1:]:
        nxt = nxt.replace("\xad", "")
        if not nxt:
            continue
        # Klassische Silbentrennung am Zeilenende: „transla-“ + „tion“ -> „translation“
        if (
            out.endswith("-")
            and len(out) >= 2
            and out[-2].isalpha()
            and nxt[0].islower()
        ):
            out = out[:-1] + nxt
        else:
            out = f"{out} {nxt}"
    return " ".join(out.split())


def extract_book(
    path: str | Path,
    ocr: bool = True,
    progress_cb=None,
    ocr_backend: str = "local",
    api_key: str = "",
) -> PdfBook:
    """Liest ein PDF ein und liefert ein PdfBook mit Kapiteln und Absätzen.

    Seiten ohne Textebene (eingescannt) werden per OCR erkannt, sofern ocr=True.
    ocr_backend: "local" (RapidOCR, offline) oder "mistral" (Mistral-OCR-API; nur mit
    api_key, gedacht für den Online-Betrieb – Seitenbilder werden dann an Mistral gesendet).
    progress_cb(page_nr, page_gesamt, modus) – modus ist "Text" oder "OCR".

    Raises:
        ScannedPdfError: wenn OCR ausgeschaltet ist und eine Seite nur Bilder enthält.
        PdfError: bei sonstigen Leseproblemen.
    """
    from . import ocr_reader

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
        page_count = len(pages_dicts)

        for index, page_dict in enumerate(pages_dicts, start=1):
            if not _page_has_text(page_dict) and not ocr:
                raise ScannedPdfError(index)

        body_size = _body_size([d for d in pages_dicts if _page_has_text(d)])
        running_margins = _detect_running_headers_footers(pages_dicts)
        chapters: list[Chapter] = []
        current = Chapter(title=None)
        chapters.append(current)

        for page_number, page_dict in enumerate(pages_dicts, start=1):
            if not _page_has_text(page_dict):
                if not ocr:
                    raise ScannedPdfError(page_number)
                if progress_cb is not None:
                    progress_cb(page_number, page_count, "OCR")
                if ocr_backend == "mistral":
                    from . import mistral_ocr

                    try:
                        markdown = mistral_ocr.ocr_page_markdown(doc[page_number - 1], api_key)
                    except mistral_ocr.MistralOcrError as exc:
                        raise PdfError(f"Seite {page_number}: {exc}") from exc
                    for text, is_heading in mistral_ocr.markdown_to_blocks(markdown):
                        if _PAGE_NUMBER_RE.match(text):
                            continue
                        if is_heading:
                            current = Chapter(title=text)
                            chapters.append(current)
                        else:
                            current.paragraphs.append(Paragraph(text, page_number))
                    continue
                if not ocr_reader.ocr_available():
                    raise PdfError(
                        f"Seite {page_number} enthält keine Textebene (nur Bilder), und das OCR-Modul "
                        "ist nicht verfügbar. Bitte Anwendung neu installieren oder OCR ausschalten."
                    )
                ocr_lines = ocr_reader.ocr_page_lines(doc[page_number - 1])
                prev_y: float | None = None
                paragraph_parts: list[str] = []

                def flush_ocr() -> None:
                    nonlocal paragraph_parts, prev_y
                    text = _join_lines(paragraph_parts).strip()
                    if text and not _PAGE_NUMBER_RE.match(text):
                        current.paragraphs.append(Paragraph(text, page_number))
                    paragraph_parts = []

                for line in ocr_lines:
                    if _PAGE_NUMBER_RE.match(line.text):
                        continue
                    gap = (line.y - prev_y) if prev_y is not None else None
                    new_paragraph = prev_y is not None and gap is not None and gap > line.height * 1.6
                    if new_paragraph:
                        flush_ocr()
                    if _ocr_heading(line.text, prev_y if not new_paragraph else None, line.y, line.height):
                        flush_ocr()
                        current = Chapter(title=line.text)
                        chapters.append(current)
                    else:
                        paragraph_parts.append(line.text)
                    prev_y = line.y
                flush_ocr()
                continue

            if progress_cb is not None:
                progress_cb(page_number, page_count, "Text")
            text_blocks_raw = []
            for block in page_dict.get("blocks", []):
                if block.get("type", 0) != 0:
                    continue
                block_lines: list[tuple[str, float, bool]] = []
                for line in block.get("lines", []):
                    text, size, bold = _line_info(line)
                    if text:
                        block_lines.append((text, size, bold))
                if block_lines:
                    text_blocks_raw.append(block_lines)

            for b_idx, block_lines in enumerate(text_blocks_raw):
                first_text, first_size, first_bold = block_lines[0]
                if _PAGE_NUMBER_RE.match(first_text):
                    continue
                # Wiederkehrende Kopf-/Fußzeilen am Seitenanfang/-ende überspringen
                if running_margins and (b_idx == 0 or b_idx == len(text_blocks_raw) - 1):
                    joined_block = " ".join(t for t, _, _ in block_lines)
                    if _normalize_margin_text(joined_block) in running_margins:
                        continue
                is_heading = (
                    first_size > body_size * 1.15
                    or (first_bold and first_size >= body_size * 1.02 and len(first_text) <= 120)
                ) and len(first_text) <= 160
                if is_heading:
                    current = Chapter(title=first_text)
                    chapters.append(current)
                    rest = _join_lines([t for t, _, _ in block_lines[1:]])
                    if rest:
                        current.paragraphs.append(Paragraph(rest, page_number))
                else:
                    text = _join_lines([t for t, _, _ in block_lines])
                    current.paragraphs.append(Paragraph(text, page_number))

        chapters = [c for c in chapters if c.paragraphs or c.title]
        if not chapters:
            raise PdfError("Im PDF wurde kein Text gefunden.")

        return PdfBook(
            path=path,
            title=title,
            author=author,
            page_count=page_count,
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
