"""EPUB-3-Ausgabe für den Tolino-Reader (ohne DRM).

- Metadaten: dc:title (deutscher Titel), dc:creator, dc:language = "de"
- navigation document (nav) UND NCX für ältere Reader
- ein Kapitel pro HTML-Datei, echte <p>-Absätze, UTF-8
- typografische Anführungszeichen im Deutschen (»…«)
- Titelseite mit Hinweis „Deutsche Übersetzung, automatisch erstellt“
- optional Deckbild aus der ersten PDF-Seite
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path

from ebooklib import epub

from .pdf_reader import Chapter, PdfBook
from .translator_base import Chunk

FAILED_NOTE = "Hinweis: Dieser Abschnitt konnte nicht übersetzt werden und ist im Original Englisch geblieben."

CSS = (
    "body { font-family: Georgia, 'Times New Roman', serif; line-height: 1.5; margin: 1em; }\n"
    "h1 { font-size: 1.4em; margin-bottom: 0.4em; }\n"
    "p { margin: 0 0 0.8em 0; text-align: justify; hyphens: auto; }\n"
    ".titlepage { text-align: center; margin-top: 30%; }\n"
    ".titlepage h1 { font-size: 1.8em; }\n"
    ".titlepage .note { font-style: italic; margin-top: 2em; }\n"
    ".failed-note { font-style: italic; color: #555; }\n"
)

def to_german_quotes(text: str) -> str:
    """Wandelt gepaarte gerade doppelte Anführungszeichen in »…« um."""
    out: list[str] = []
    opening = True
    for ch in text:
        if ch == '"':
            out.append("»" if opening else "«")
            opening = not opening
        else:
            out.append(ch)
    return "".join(out)


def sanitize_filename(name: str) -> str:
    """Bereinigt einen Dateinamen für die EPUB-Ausgabe."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip().strip(".")
    return cleaned or "buch"


def output_filename(original_title: str) -> str:
    return f"{sanitize_filename(original_title)} (deutsch).epub"


def _paragraphs_to_html(text: str) -> str:
    parts: list[str] = []
    for para in re.split(r"\n\s*\n", text.strip()):
        para = para.strip()
        if not para:
            continue
        para = to_german_quotes(para)
        para = html.escape(para, quote=False)
        para = para.replace("\n", "<br/>")
        parts.append(f"<p>{para}</p>")
    return "\n".join(parts)


def _xhtml(title: str, body_html: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="de">\n'
        "<head>\n"
        '  <meta charset="utf-8"/>\n'
        f"  <title>{html.escape(title)}</title>\n"
        '  <link rel="stylesheet" type="text/css" href="style.css"/>\n'
        "</head>\n"
        f"<body>\n{body_html}\n</body>\n</html>\n"
    )


@dataclass
class EpubResult:
    path: Path
    failed_chunks: int


def build_epub(
    book: PdfBook,
    chunks: list[Chunk],
    translations: dict[int, str | None],  # chunk.index -> übersetzter Text (None = fehlgeschlagen)
    out_path: str | Path,
    title_de: str | None = None,
    cover_png: bytes | None = None,
    chapter_titles_de: dict[int, str] | None = None,
) -> EpubResult:
    """Erzeugt die EPUB-Datei. translations[index] = None erzeugt eine Notiz im Kapitel."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    chapter_titles_de = chapter_titles_de or {}

    if title_de is None:
        first_idx = next((i for i, ch in enumerate(book.chapters) if ch.title), None)
        if first_idx is not None and first_idx in chapter_titles_de:
            title_de = chapter_titles_de[first_idx]
        else:
            title_de = book.first_chapter_title or book.title

    failed = sum(1 for c in chunks if translations.get(c.index) is None)

    epub_book = epub.EpubBook()
    epub_book.set_identifier(f"urn:gideons-uebersetzer:{book.path.name}")
    epub_book.set_title(title_de)
    epub_book.set_language("de")
    epub_book.add_author(book.author or "Unbekannt")

    css_item = epub.EpubItem(
        uid="style", file_name="style.css", media_type="text/css", content=CSS
    )
    epub_book.add_item(css_item)

    if cover_png:
        epub_book.set_cover("cover.png", cover_png)

    # Titelseite
    title_html = _xhtml(
        title_de,
        '<div class="titlepage">\n'
        f"<h1>{html.escape(title_de)}</h1>\n"
        f"<p>{html.escape(book.author or 'Unbekannt')}</p>\n"
        '<p class="note">Deutsche Übersetzung, automatisch erstellt</p>\n'
        "</div>",
    )
    title_item = epub.EpubHtml(uid="titlepage", file_name="titlepage.xhtml", lang="de")
    title_item.content = title_html
    title_item.add_item(css_item)
    epub_book.add_item(title_item)

    # Kapitel gruppieren
    chapter_texts: dict[int, list[str]] = {i: [] for i in range(len(book.chapters))}
    for chunk in sorted(chunks, key=lambda c: c.index):
        translation = translations.get(chunk.index)
        if translation is None:
            chapter_texts[chunk.chapter_index].append(f'<p class="failed-note">{FAILED_NOTE}</p>')
        else:
            chapter_texts[chunk.chapter_index].append(_paragraphs_to_html(translation))

    toc_entries = [epub.Link("titlepage.xhtml", "Titel", "titlepage")]
    spine = [title_item]
    for i, chapter in enumerate(book.chapters):
        translated_heading = chapter_titles_de.get(i)
        raw_title = translated_heading or chapter.title
        title = raw_title or f"Kapitel {i + 1}"
        body = "\n".join(chapter_texts.get(i, [])) or "<p></p>"
        if raw_title:
            body = f"<h1>{html.escape(raw_title)}</h1>\n" + body
        item = epub.EpubHtml(uid=f"chap{i}", file_name=f"chap_{i}.xhtml", lang="de", title=title)
        item.content = _xhtml(title, body)
        item.add_item(css_item)
        epub_book.add_item(item)
        epub_book.spine.append(item)
        toc_entries.append(epub.Link(f"chap_{i}.xhtml", title, f"chap{i}"))

    epub_book.add_item(epub.EpubNav())
    epub_book.add_item(epub.EpubNcx())
    epub_book.toc = toc_entries
    if cover_png:
        epub_book.spine.insert(0, "cover")
    epub_book.spine.insert(0, "nav")

    epub.write_epub(str(out_path), epub_book, {})
    return EpubResult(path=out_path, failed_chunks=failed)
