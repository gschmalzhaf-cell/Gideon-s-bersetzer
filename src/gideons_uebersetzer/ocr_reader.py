"""OCR für gescannte PDF-Seiten (RapidOCR/ONNX – vollständig lokal, ohne Tesseract-Installation).

Wird nur bei Seiten ohne Textebene aktiv. Das ONNX-Modell ist im Paket
enthalten und wird zur Laufzeit einmalig geladen.
"""

from __future__ import annotations

from dataclasses import dataclass

import pymupdf

OCR_DPI = 200


class OcrUnavailableError(Exception):
    """Das OCR-Modul ist nicht installiert/verfügbar."""


@dataclass
class OcrLine:
    text: str
    y: float  # vertikale Mitte der Zeile (in Pixeln des OCR-Bildes)
    height: float


_engine = None


def ocr_available() -> bool:
    try:
        import rapidocr_onnxruntime  # noqa: F401

        return True
    except Exception:
        return False


def _get_engine():
    global _engine
    if _engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except Exception as exc:
            raise OcrUnavailableError(
                "Das OCR-Modul (rapidocr-onnxruntime) ist nicht installiert. "
                "Bitte Anwendung neu installieren oder OCR in den Einstellungen ausschalten."
            ) from exc
        _engine = RapidOCR()
    return _engine


def ocr_page_lines(page: "pymupdf.Page") -> list[OcrLine]:
    """Erkennt den Text einer PDF-Seite per OCR und liefert Zeilen mit Position."""
    import cv2
    import numpy as np

    zoom = OCR_DPI / 72.0
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    arr = cv2.imdecode(np.frombuffer(pix.tobytes("png"), np.uint8), cv2.IMREAD_COLOR)
    result, _ = _get_engine()(arr)
    lines: list[OcrLine] = []
    for entry in result or []:
        box = entry[0]
        rest = entry[1]
        # je nach RapidOCR-Version: [box, text, score] oder [box, (text, score)]
        text = rest[0] if isinstance(rest, (list, tuple)) else rest
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        height = max(ys) - min(ys)
        lines.append(OcrLine(text=text.strip(), y=(min(ys) + max(ys)) / 2, height=height))
    lines.sort(key=lambda l: (l.y, l.height))
    return [l for l in lines if l.text]
