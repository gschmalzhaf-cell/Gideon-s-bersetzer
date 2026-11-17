"""Allgemeiner Dokument-Import: PDF (PyMuPDF/OCR), EPUB (ebooklib) und DOCX (python-docx).

Alle Formate liefern dieselbe PdfBook-Struktur (Kapitel + Absätze), damit Pipeline und
EPUB-Ausgabe unverändert bleiben. Seitenzahlen sind bei EPUB/DOCX gegenstandslos (page=1).
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

from . import pdf_reader
from .pdf_reader import Chapter, Paragraph, PdfBook, PdfError

SUPPORTED_SUFFIXES = (".pdf", ".epub", ".docx")


def read_book(
    path: str | Path,
    ocr: bool = True,
    progress_cb=None,
    ocr_backend: str = "local",
    api_key: str = "",
) -> PdfBook:
    """Liest ein Dokument (PDF/EPUB/DOCX) und liefert ein PdfBook."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return pdf_reader.extract_book(path, ocr=ocr, progress_cb=progress_cb, ocr_backend=ocr_backend, api_key=api_key)
    if suffix == ".epub":
        return _read_epub(path)
    if suffix == ".docx":
        return _read_docx(path)
    raise PdfError(f"Nicht unterstütztes Format: '{suffix or path.name}' (erlaubt: {', '.join(SUPPORTED_SUFFIXES)})")


class _EpubHtmlParser(HTMLParser):
    """Zerlegt EPUB-HTML in Blöcke (Text, ist_ueberschrift)."""

    HEADING_TAGS = {"h1", "h2", "h3", "h4"}

    def __init__(self):
        super().__init__()
        self.blocks: list[tuple[str, bool]] = []
        self._buf: list[str] = []
        self._heading = False
        self._skip = 0  # script/style/titelei ignorieren

    def _flush(self, heading: bool) -> None:
        text = " ".join("".join(self._buf).split())
        self._buf = []
        if text:
            self.blocks.append((text, heading))

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
            return
        if self._skip:
            return
        if tag in self.HEADING_TAGS:
            self._flush(False)
            self._heading = True
            self._buf = []
        elif tag in ("p", "br", "div", "li", "tr"):
            self._flush(self._heading)
            self._heading = False

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
            return
        if self._skip:
            return
        if tag in self.HEADING_TAGS:
            self._flush(True)
            self._heading = False
        elif tag in ("p", "div", "li", "tr"):
            self._flush(False)

    def handle_data(self, data):
        if not self._skip:
            self._buf.append(data)

    def close(self):
        super().close()
        self._flush(self._heading)


def _read_epub(path: Path) -> PdfBook:
    try:
        import ebooklib
        from ebooklib import epub
    except ImportError as exc:
        raise PdfError("EPUB-Unterstützung fehlt (ebooklib nicht installiert).") from exc
    try:
        ebook = epub.read_epub(str(path))
    except Exception as exc:
        raise PdfError(f"Die EPUB konnte nicht gelesen werden: {path.name} ({exc})") from exc

    title_meta = ebook.get_metadata("DC", "title")
    author_meta = ebook.get_metadata("DC", "creator")
    title = (title_meta[0][0] if title_meta else "") or path.stem
    author = (author_meta[0][0] if author_meta else "") or "Unbekannt"

    items = [i for i in ebook.get_items() if i.get_type() == ebooklib.ITEM_DOCUMENT]
    id_to_item = {i.get_id(): i for i in items}
    ordered = [id_to_item[sid] for sid, _linear in ebook.spine if sid in id_to_item]
    if not ordered:
        ordered = items

    chapters: list[Chapter] = []
    current = Chapter(title=None)
    chapters.append(current)
    item_count = 0
    for item in ordered:
        item_count += 1
        html = item.get_content().decode("utf-8", errors="replace")
        parser = _EpubHtmlParser()
        parser.feed(html)
        parser.close()
        for text, is_heading in parser.blocks:
            if is_heading:
                current = Chapter(title=text)
                chapters.append(current)
            else:
                current.paragraphs.append(Paragraph(text, 1))

    chapters = [c for c in chapters if c.paragraphs or c.title]
    if not chapters:
        raise PdfError(f"In der EPUB wurde kein Text gefunden: {path.name}")
    return PdfBook(path=path, title=title, author=author, page_count=item_count, chapters=chapters)


def _read_docx(path: Path) -> PdfBook:
    try:
        import docx
    except ImportError as exc:
        raise PdfError("DOCX-Unterstützung fehlt (python-docx nicht installiert).") from exc
    try:
        doc = docx.Document(str(path))
    except Exception as exc:
        raise PdfError(f"Das DOCX konnte nicht gelesen werden: {path.name} ({exc})") from exc

    title = (doc.core_properties.title or "").strip() or path.stem
    author = (doc.core_properties.author or "").strip() or "Unbekannt"

    chapters: list[Chapter] = []
    current = Chapter(title=None)
    chapters.append(current)
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style = (para.style.name if para.style else "").lower()
        if style.startswith("heading") or style == "title":
            current = Chapter(title=text)
            chapters.append(current)
        else:
            current.paragraphs.append(Paragraph(text, 1))

    chapters = [c for c in chapters if c.paragraphs or c.title]
    if not chapters:
        raise PdfError(f"Im DOCX wurde kein Text gefunden: {path.name}")
    return PdfBook(path=path, title=title, author=author, page_count=0, chapters=chapters)
