import base64

import pymupdf
import pytest

from gideons_uebersetzer import mistral_ocr


def test_markdown_to_blocks():
    md = "# Kapitel Eins\n\nErster Absatz mit\nhartem Umbruch.\n\nZweiter Absatz.\n\n![bild](x.png)\n"
    blocks = mistral_ocr.markdown_to_blocks(md)
    assert blocks == [
        ("Kapitel Eins", True),
        ("Erster Absatz mit hartem Umbruch.", False),
        ("Zweiter Absatz.", False),
    ]


class FakeResp:
    def __init__(self, data, status_code=200, text=""):
        self._data = data
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._data


def test_ocr_page_markdown_payload_and_parse(monkeypatch, scanned_pdf):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured.update(url=url, json=json, headers=headers)
        return FakeResp({"pages": [{"index": 0, "markdown": "# Titel\n\nText der Seite."}], "model": "mistral-ocr-latest"})

    monkeypatch.setattr(mistral_ocr.requests, "post", fake_post)
    with pymupdf.open(scanned_pdf) as doc:
        md = mistral_ocr.ocr_page_markdown(doc[0], "KEY")
    assert md == "# Titel\n\nText der Seite."
    assert captured["url"] == mistral_ocr.OCR_ENDPOINT
    assert captured["json"]["model"] == "mistral-ocr-latest"
    assert captured["json"]["document"]["type"] == "image_url"
    img = captured["json"]["document"]["image_url"]
    assert img.startswith("data:image/png;base64,")
    assert base64.b64decode(img.split(",", 1)[1])[:8] == b"\x89PNG\r\n\x1a\n"
    assert captured["headers"]["Authorization"] == "Bearer KEY"


def test_ocr_page_markdown_requires_key(scanned_pdf):
    with pymupdf.open(scanned_pdf) as doc:
        with pytest.raises(mistral_ocr.MistralOcrError, match="API-Schlüssel"):
            mistral_ocr.ocr_page_markdown(doc[0], "")


def test_ocr_page_markdown_http_error(monkeypatch, scanned_pdf):
    def fake_post(url, json=None, headers=None, timeout=None):
        return FakeResp({}, status_code=401, text="unauthorized")

    monkeypatch.setattr(mistral_ocr.requests, "post", fake_post)
    with pymupdf.open(scanned_pdf) as doc:
        with pytest.raises(mistral_ocr.MistralOcrError, match="401"):
            mistral_ocr.ocr_page_markdown(doc[0], "KEY")


def test_extract_book_with_mistral_backend(monkeypatch, scanned_pdf):
    from gideons_uebersetzer import pdf_reader

    monkeypatch.setattr(
        mistral_ocr,
        "ocr_page_markdown",
        lambda page, key: "# Kapitel Eins\n\nErster Absatz der Seite. Zweiter Satz hier.",
    )
    book = pdf_reader.extract_book(scanned_pdf, ocr=True, ocr_backend="mistral", api_key="KEY")
    assert any(c.title == "Kapitel Eins" for c in book.chapters)
    assert any("Erster Absatz der Seite." in p.text for c in book.chapters for p in c.paragraphs)
