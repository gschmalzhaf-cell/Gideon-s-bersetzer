import pytest

from gideons_uebersetzer import pdf_reader


def test_extract_book_detects_chapters(sample_pdf):
    book = pdf_reader.extract_book(sample_pdf)
    assert book.title == "Sample Book"
    assert book.author == "Jane Doe"
    assert book.page_count == 3
    assert len(book.chapters) >= 2
    titles = [c.title for c in book.chapters if c.title]
    assert any("Chapter 1" in t for t in titles)
    assert book.word_count > 50
    for chapter in book.chapters:
        for para in chapter.paragraphs:
            assert 1 <= para.page <= book.page_count


def test_scanned_pdf_raises_clear_german_message(scanned_pdf):
    with pytest.raises(pdf_reader.ScannedPdfError) as excinfo:
        pdf_reader.extract_book(scanned_pdf, ocr=False)
    message = str(excinfo.value)
    assert "keine Textebene" in message
    assert "OCR ist ausgeschaltet" in message
    assert "Seite 1" in message


def test_missing_file_raises_pdf_error(tmp_path):
    with pytest.raises(pdf_reader.PdfError):
        pdf_reader.extract_book(tmp_path / "fehlt.pdf")


def test_cover_extraction(sample_pdf):
    png = pdf_reader.extract_cover_png(sample_pdf)
    assert png is not None
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
