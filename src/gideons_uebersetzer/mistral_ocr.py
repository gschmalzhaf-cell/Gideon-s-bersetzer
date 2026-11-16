"""OCR für gescannte PDF-Seiten über die Mistral-OCR-API (opt-in, nur Online-Betrieb).

WICHTIG (Privatsphäre): In diesem Modus werden die Bilder der gescannten Seiten an
Mistral (api.mistral.ai) übertragen. Text-Seiten des PDF werden nicht gesendet.
Nur aktiv, wenn der Online-Betrieb bewusst eingeschaltet ist UND das OCR-Backend
"mistral" gewählt wurde (Einstellungen/CLI); Standard bleibt lokales RapidOCR.
"""

from __future__ import annotations

import base64

import pymupdf
import requests

OCR_MODEL = "mistral-ocr-latest"
OCR_ENDPOINT = "https://api.mistral.ai/v1/ocr"
OCR_DPI = 300
CONNECT_TIMEOUT = 15
READ_TIMEOUT = 300


class MistralOcrError(Exception):
    """OCR-API-Fehler mit deutscher, anzeigbarer Meldung."""


def markdown_to_blocks(markdown: str) -> list[tuple[str, bool]]:
    """Wandelt Mistral-OCR-Markdown in (Text, ist_ueberschrift)-Blöcke um.

    Zeilen mit führendem '#' werden als Kapitelüberschriften markiert, Leerzeilen
    trennen Absätze; harte Zeilenumbrüche innerhalb eines Absatzes werden zu
    Leerzeichen (Mistral liefert oft umgebrochene Zeilen).
    """
    blocks: list[tuple[str, bool]] = []
    paragraph: list[str] = []

    def flush() -> None:
        text = " ".join(paragraph).strip()
        if text:
            blocks.append((text, False))
        paragraph.clear()

    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        if line.startswith("#"):
            flush()
            title = line.lstrip("#").strip()
            if title:
                blocks.append((title, True))
            continue
        if line.startswith("!["):  # eingebettete Bilder/Tags überspringen
            continue
        paragraph.append(line)
    flush()
    return blocks


def ocr_page_markdown(page: "pymupdf.Page", api_key: str, endpoint: str = OCR_ENDPOINT) -> str:
    """Sendet das Seitenbild an die Mistral-OCR-API und liefert den Markdown-Text der Seite."""
    if not api_key:
        raise MistralOcrError("Für Mistral OCR wird ein API-Schlüssel benötigt (Einstellungen).")
    zoom = OCR_DPI / 72.0
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    b64 = base64.b64encode(pix.tobytes("png")).decode("ascii")
    payload = {
        "model": OCR_MODEL,
        "document": {"type": "image_url", "image_url": f"data:image/png;base64,{b64}"},
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
    except requests.RequestException as exc:
        raise MistralOcrError(f"Die Mistral-OCR-API ist nicht erreichbar: {exc}") from exc
    if response.status_code != 200:
        if response.status_code == 401:
            msg = "Der API-Schlüssel wurde von Mistral abgelehnt (HTTP 401). Bitte Schlüssel prüfen."
        elif response.status_code == 429:
            msg = "Zu viele Anfragen bei Mistral OCR (HTTP 429). Bitte kurz warten und erneut versuchen."
        else:
            msg = f"Mistral-OCR-Fehler (HTTP {response.status_code}): {response.text[:200]}"
        raise MistralOcrError(msg)
    try:
        data = response.json()
        pages = data.get("pages") or []
        markdown = pages[0].get("markdown", "") if pages else ""
    except ValueError as exc:
        raise MistralOcrError("Unerwartete Antwort der Mistral-OCR-API (kein JSON).") from exc
    if not markdown.strip():
        raise MistralOcrError("Mistral OCR hat auf dieser Seite keinen Text erkannt.")
    return markdown
