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


@pytest.fixture()
def sample_pdf(tmp_path):
    return make_text_pdf(tmp_path / "sample.pdf")


@pytest.fixture()
def scanned_pdf(tmp_path):
    return make_scanned_pdf(tmp_path / "scanned.pdf")
