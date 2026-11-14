import xml.etree.ElementTree as ET
import zipfile

from ebooklib import epub

from gideons_uebersetzer import epub_builder, pdf_reader
from gideons_uebersetzer.translator_base import split_into_chunks


def _build(tmp_path, sample_pdf, fail_index=None):
    book = pdf_reader.extract_book(sample_pdf)
    chunks = split_into_chunks(book.chapters, 60)
    translations = {}
    for c in chunks:
        translations[c.index] = None if c.index == fail_index else f'Übersetzter Text »für« Abschnitt {c.index}. "Zitat" bleibt geschützt.'
    out = tmp_path / "out" / epub_builder.output_filename(book.title)
    result = epub_builder.build_epub(book, chunks, translations, out, cover_png=pdf_reader.extract_cover_png(sample_pdf))
    return book, result


def test_epub_structure_and_metadata(tmp_path, sample_pdf):
    book, result = _build(tmp_path, sample_pdf)
    assert result.path.is_file()
    assert result.path.name == "Sample Book (deutsch).epub"

    with zipfile.ZipFile(result.path) as zf:
        names = set(zf.namelist())
        assert "META-INF/container.xml" in names
        assert "EPUB/nav.xhtml" in names or any(n.endswith("nav.xhtml") for n in names)
        assert any(n.endswith("toc.ncx") for n in names)
        opf = [n for n in names if n.endswith(".opf")][0]
        opf_xml = zf.read(opf).decode("utf-8")
        assert 'lang="de"' in opf_xml or "<dc:language>de</dc:language>" in opf_xml
        assert "Sample Book" in opf_xml or "Chapter" in opf_xml  # deutscher Titel aus erstem Kapitelkopf
        assert "Jane Doe" in opf_xml
        # alle XHTML-Dateien müssen wohlgeformtes XML sein
        for name in names:
            if name.endswith((".xhtml", ".xml", ".opf", ".ncx")):
                ET.fromstring(zf.read(name))
        # Titelseite mit Hinweis
        title = [n for n in names if "titlepage" in n][0]
        assert "Deutsche Übersetzung, automatisch erstellt" in zf.read(title).decode("utf-8")
        # Kapitel mit <p>-Absätzen und deutschen Anführungszeichen
        chap = [n for n in names if n.startswith("EPUB/chap_")][0]
        content = zf.read(chap).decode("utf-8")
        assert "<p>" in content
        assert "»für«" in content


def test_epub_reopens_with_ebooklib(tmp_path, sample_pdf):
    book, result = _build(tmp_path, sample_pdf)
    loaded = epub.read_epub(str(result.path))
    assert loaded.get_metadata("DC", "language") == [("de", {})] or loaded.language == "de"
    titles = loaded.get_metadata("DC", "title")
    assert titles
    items = list(loaded.get_items())
    html_items = [i for i in items if i.get_type() == 9]
    assert len(html_items) >= len(book.chapters) + 1  # Kapitel + Titelseite


def test_failed_chunk_inserts_note(tmp_path, sample_pdf):
    book, result = _build(tmp_path, sample_pdf, fail_index=0)
    assert result.failed_chunks == 1
    with zipfile.ZipFile(result.path) as zf:
        chap0 = zf.read("EPUB/chap_0.xhtml").decode("utf-8")
    assert "konnte nicht übersetzt werden" in chap0


def test_german_quotes_pairing():
    assert epub_builder.to_german_quotes('Er sagte "Hallo" und ging.') == "Er sagte »Hallo« und ging."
    assert epub_builder.to_german_quotes('"Anfang" Mitte "Ende"') == "»Anfang« Mitte »Ende«"


def test_output_filename_sanitized():
    assert epub_builder.output_filename('Mein Buch: Teil 1?') == "Mein Buch_ Teil 1_ (deutsch).epub"
