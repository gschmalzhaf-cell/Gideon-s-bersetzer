import sys
from pathlib import Path

import pymupdf
import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

BODY_SIZE = 11.0
HEADING_SIZE = 18.0


def make_text_pdf(path: Path, pages: int = 3, paragraphs_per_page: int = 3) -> Path:
    """Erzeugt ein einfaches Text-PDF mit Kapiteln (große fette Überschriften)."""
    doc = pymupdf.open()
    for page_no in range(pages):
        page = doc.new_page()
        y = 60
        if page_no % 2 == 0:
            page.insert_text((50, y), f"Chapter {page_no + 1}: The Beginning", fontsize=HEADING_SIZE, fontname="hebo")
            y += 40
        for i in range(paragraphs_per_page):
            text = (
                f"This is paragraph {i + 1} on page {page_no + 1} of the sample book. "
                "It contains plain English sentences that the translator should render into German. "
                'He said "hello" and she answered "goodbye". '
            )
            page.insert_textbox(
                pymupdf.Rect(50, y, 545, y + 60), text, fontsize=BODY_SIZE, fontname="helv"
            )
            y += 70
    doc.set_metadata({"title": "Sample Book", "author": "Jane Doe"})
    doc.save(path)
    doc.close()
    return path


def make_scanned_pdf(path: Path) -> Path:
    """Erzeugt ein PDF ohne Textebene (nur Bild)."""
    doc = pymupdf.open()
    page = doc.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 200))
    pix.clear_with(120)
    page.insert_image(page.rect, pixmap=pix)
    doc.save(path)
    doc.close()
    return path


def make_scan_pdf_from(text_pdf: Path, out: Path, pages: int | None = None, zoom: float = 2.5) -> Path:
    """Rendert Text-Seiten als Bild in ein neues PDF ohne Textebene (Scan-Simulation)."""
    doc = pymupdf.open(text_pdf)
    scan = pymupdf.open()
    for i, page in enumerate(doc):
        if pages is not None and i >= pages:
            break
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        sp = scan.new_page(width=page.rect.width, height=page.rect.height)
        sp.insert_image(sp.rect, pixmap=pix)
    scan.save(out)
    scan.close()
    doc.close()
    return out


def make_mixed_pdf(text_pdf: Path, out: Path) -> Path:
    """Seite 1 als Text, Seite 2+ als Scan."""
    doc = pymupdf.open(text_pdf)
    scan_page = doc[1]
    pix = scan_page.get_pixmap(matrix=pymupdf.Matrix(2.5, 2.5))
    img_pdf = pymupdf.open()
    sp = img_pdf.new_page(width=scan_page.rect.width, height=scan_page.rect.height)
    sp.insert_image(sp.rect, pixmap=pix)
    img_bytes = img_pdf.tobytes()
    doc.close()
    mixed = pymupdf.open("pdf", img_bytes)
    final = pymupdf.open(text_pdf)
    final.delete_page(1)
    final.insert_pdf(mixed)
    final.save(out)
    final.close()
    return out


@pytest.fixture()
def sample_pdf(tmp_path):
    return make_text_pdf(tmp_path / "sample.pdf")


@pytest.fixture()
def scanned_pdf(tmp_path):
    return make_scanned_pdf(tmp_path / "scanned.pdf")


@pytest.fixture()
def scan_pdf(tmp_path, sample_pdf):
    return make_scan_pdf_from(sample_pdf, tmp_path / "scan.pdf")
