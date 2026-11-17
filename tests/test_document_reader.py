import pytest

from gideons_uebersetzer import document_reader
from gideons_uebersetzer.pdf_reader import PdfError


def _make_epub(path):
    from ebooklib import epub

    book = epub.EpubBook()
    book.set_identifier("sample-epub")
    book.set_title("Sample EPUB")
    book.add_author("Jane Doe")
    c1 = epub.EpubHtml(title="Chapter 1", file_name="ch1.xhtml", lang="en")
    c1.content = "<h1>Chapter One</h1><p>First paragraph of the book.</p><p>Second paragraph here.</p>"
    c2 = epub.EpubHtml(title="Chapter 2", file_name="ch2.xhtml", lang="en")
    c2.content = "<h2>Chapter Two</h2><p>More text in chapter two.</p>"
    book.add_item(c1)
    book.add_item(c2)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.toc = (c1, c2)
    book.spine = ["nav", c1, c2]
    epub.write_epub(str(path), book)


def _make_docx(path):
    import docx

    doc = docx.Document()
    doc.core_properties.title = "Sample DOCX"
    doc.core_properties.author = "Jane Doe"
    doc.add_heading("Chapter One", level=1)
    doc.add_paragraph("First paragraph of the docx file.")
    doc.add_paragraph("Second paragraph, still chapter one.")
    doc.add_heading("Chapter Two", level=2)
    doc.add_paragraph("Text of the second chapter.")
    doc.save(str(path))


def test_read_epub_detects_chapters_and_paragraphs(tmp_path):
    epub_path = tmp_path / "book.epub"
    _make_epub(epub_path)
    book = document_reader.read_book(epub_path)
    assert book.title == "Sample EPUB"
    assert book.author == "Jane Doe"
    titles = [c.title for c in book.chapters]
    assert "Chapter One" in titles and "Chapter Two" in titles
    all_text = " ".join(p.text for c in book.chapters for p in c.paragraphs)
    assert "First paragraph of the book." in all_text
    assert "More text in chapter two." in all_text
    assert book.word_count > 10


def test_read_docx_detects_headings_and_paragraphs(tmp_path):
    docx_path = tmp_path / "book.docx"
    _make_docx(docx_path)
    book = document_reader.read_book(docx_path)
    assert book.title == "Sample DOCX"
    titles = [c.title for c in book.chapters]
    assert "Chapter One" in titles and "Chapter Two" in titles
    all_text = " ".join(p.text for c in book.chapters for p in c.paragraphs)
    assert "First paragraph of the docx file." in all_text
    assert "Text of the second chapter." in all_text


def test_read_pdf_dispatch(tmp_path, sample_pdf):
    book = document_reader.read_book(sample_pdf)
    assert book.path.suffix == ".pdf"
    assert book.word_count > 0


def test_unsupported_suffix_rejected(tmp_path):
    txt = tmp_path / "notes.txt"
    txt.write_text("hello", encoding="utf-8")
    with pytest.raises(PdfError, match="Nicht unterstütztes Format"):
        document_reader.read_book(txt)


def test_missing_file_rejected(tmp_path):
    with pytest.raises(PdfError):
        document_reader.read_book(tmp_path / "gibts-nicht.epub")
