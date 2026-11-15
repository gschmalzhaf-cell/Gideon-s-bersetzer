import pytest

from gideons_uebersetzer import ocr_reader, pdf_reader
from gideons_uebersetzer.ocr_reader import OcrLine

FAKE_OCR_LINES = [
    OcrLine("Chapter 1: The Beginning", y=50, height=30),
    OcrLine("This is the first paragraph of the scanned page.", y=110, height=12),
    OcrLine("It continues with more text for the translator.", y=130, height=12),
    OcrLine("Second paragraph starts here after a gap.", y=200, height=12),
]


def _patch_ocr(monkeypatch, lines=FAKE_OCR_LINES):
    monkeypatch.setattr(ocr_reader, "ocr_available", lambda: True)
    monkeypatch.setattr(ocr_reader, "ocr_page_lines", lambda page: list(lines))


def test_scanned_pdf_without_ocr_raises_original_message(scanned_pdf):
    with pytest.raises(pdf_reader.ScannedPdfError) as excinfo:
        pdf_reader.extract_book(scanned_pdf, ocr=False)
    message = str(excinfo.value)
    assert "keine Textebene" in message
    assert "OCR ist ausgeschaltet" in message


def test_scanned_pdf_with_ocr_extracts_text(scanned_pdf, monkeypatch):
    _patch_ocr(monkeypatch)
    progress = []
    book = pdf_reader.extract_book(
        scanned_pdf, ocr=True, progress_cb=lambda p, t, m: progress.append((p, t, m))
    )
    assert any(m == "OCR" for _, _, m in progress)
    titles = [c.title for c in book.chapters if c.title]
    assert "Chapter 1: The Beginning" in titles
    all_text = " ".join(p.text for c in book.chapters for p in c.paragraphs)
    assert "first paragraph of the scanned page" in all_text
    assert "Second paragraph starts here" in all_text
    assert book.word_count > 10


def test_mixed_pdf_uses_text_and_ocr(tmp_path, sample_pdf, monkeypatch):
    from conftest import make_mixed_pdf

    mixed = make_mixed_pdf(sample_pdf, tmp_path / "mixed.pdf")
    _patch_ocr(monkeypatch)
    book = pdf_reader.extract_book(mixed, ocr=True)
    all_text = " ".join(p.text for c in book.chapters for p in c.paragraphs)
    assert "page 1" in all_text  # Text-Seite
    assert "scanned page" in all_text  # OCR-Seite
    assert book.page_count == 3


def test_ocr_unavailable_raises_clear_message(scanned_pdf, monkeypatch):
    monkeypatch.setattr(ocr_reader, "ocr_available", lambda: False)
    with pytest.raises(pdf_reader.PdfError) as excinfo:
        pdf_reader.extract_book(scanned_pdf, ocr=True)
    assert "OCR-Modul" in str(excinfo.value)


def test_ocr_heading_heuristic():
    assert ocr_reader  # Modul importierbar
    from gideons_uebersetzer.pdf_reader import _ocr_heading

    assert _ocr_heading("Chapter 5: A New Hope", None, 50, 30) is True  # erste Zeile, kein Satzzeichen
    assert _ocr_heading("This is a normal sentence.", 60, 110, 12) is False  # endet mit Punkt
    assert _ocr_heading("A short heading", 100, 160, 12) is True  # großer Abstand davor
    # umgebrochene Fließtext-Zeile (~90 Zeichen, abgeschnitten) ist KEINE Überschrift
    wrapped = "This is paragraph 1 on page 1 of the sample book. It contains plain English sentences that the"
    assert _ocr_heading(wrapped, 100, 130, 12) is False


@pytest.mark.skipif(not ocr_reader.ocr_available(), reason="rapidocr-onnxruntime nicht installiert")
def test_real_ocr_on_scanned_page(tmp_path, sample_pdf):
    from conftest import make_scan_pdf_from

    scan = make_scan_pdf_from(sample_pdf, tmp_path / "scan_real.pdf", pages=1)
    book = pdf_reader.extract_book(scan, ocr=True)
    all_text = " ".join(
        [c.title or "" for c in book.chapters]
        + [p.text for c in book.chapters for p in c.paragraphs]
    ).lower()
    assert "paragraph" in all_text
    assert "sample book" in all_text
    assert book.word_count > 20
