"""Gemeinsame Übersetzungslogik: Chunking, Prompts, Glossar, Qualitätsprüfung."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .pdf_reader import Chapter

MAX_RETRIES = 2  # ein misslungener Abschnitt wird bis zu zweimal erneut versucht

SYSTEM_PROMPT = (
    "Du bist ein professioneller Literaturübersetzer. Übersetze den folgenden "
    "englischen Text ins Deutsche. Antworte ausschließlich mit der Übersetzung: "
    "keine Einleitung, kein Kommentar, keine Anführungszeichen um den gesamten "
    "Text, keine Erklärungen. Behalte die Absatzstruktur des Originals bei."
)

# Modell-Antworten und Prompt-Reste, die im Ergebnis nicht vorkommen dürfen.
FORBIDDEN_MARKERS = (
    "hier ist die übersetzung",
    "here is the translation",
    "here's the translation",
    "übersetzung:",
    "translation:",
    "```",
    "<|im_start|>",
    "<|im_end|>",
    "system:",
    "zu übersetzender text",
)

# Häufige englische Stoppwörter; ein hoher Anteil deutet auf nicht übersetzten Text hin.
ENGLISH_STOPWORDS = {
    "the", "and", "of", "to", "in", "that", "is", "was", "it", "for", "on", "with",
    "as", "at", "by", "an", "be", "this", "which", "or", "from", "but", "not",
    "are", "were", "they", "he", "she", "his", "her", "you", "we", "i",
}
MAX_ENGLISH_STOPWORD_RATIO = 0.06


@dataclass
class Chunk:
    """Ein Übersetzungsabschnitt (gehört immer zu genau einem Kapitel)."""

    index: int
    chapter_index: int
    text: str
    page: int  # 1-basierte Seite, auf der der Abschnitt beginnt

    @property
    def word_count(self) -> int:
        return len(self.text.split())


class CancelledError(Exception):
    """Wird ausgelöst, wenn der Anwender die Übersetzung abbricht."""


def split_into_chunks(chapters: list[Chapter], chunk_words: int) -> list[Chunk]:
    """Gruppiert Absätze zu Abschnitten von etwa chunk_words Wörtern.

    Absätze werden nicht mitten im Satz geteilt und Kapitelgrenzen werden
    nicht überschritten.
    """
    chunk_words = max(200, int(chunk_words))
    chunks: list[Chunk] = []
    for chapter_index, chapter in enumerate(chapters):
        current_paragraphs: list[str] = []
        current_words = 0
        current_page = chapter.paragraphs[0].page if chapter.paragraphs else 1

        def flush() -> None:
            nonlocal current_paragraphs, current_words, current_page
            if current_paragraphs:
                chunks.append(
                    Chunk(
                        index=len(chunks),
                        chapter_index=chapter_index,
                        text="\n\n".join(current_paragraphs),
                        page=current_page,
                    )
                )
            current_paragraphs = []
            current_words = 0

        for paragraph in chapter.paragraphs:
            words = len(paragraph.text.split())
            if current_paragraphs and current_words + words > chunk_words:
                flush()
                current_page = paragraph.page
            current_paragraphs.append(paragraph.text)
            current_words += words
        flush()
    return chunks


def load_glossary(path: str | Path | None) -> list[tuple[str, str]]:
    """Lädt eine Glossar-Textdatei: eine Zeile 'Begriff = Übersetzung'."""
    if not path:
        return []
    path = Path(path)
    entries: list[tuple[str, str]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            term, translation = line.split("=", 1)
            term, translation = term.strip(), translation.strip()
            if term and translation:
                entries.append((term, translation))
    except OSError:
        return []
    return entries


def prompt_format_for(settings) -> str:
    """"translategemma", wenn das gewählte Modell TranslateGemma ist (eigenes Prompt-Format)."""
    haystack = f"{settings.hf_filename} {settings.model_path}".lower()
    return "translategemma" if "translategemma" in haystack else "default"


def build_messages(
    source_text: str,
    context_paragraphs: list[str],
    glossary: list[tuple[str, str]],
    extra_hint: str = "",
    fmt: str = "default",
) -> list[dict]:
    """Baut die Chat-Nachrichten für einen Übersetzungsaufruf.

    context_paragraphs: die letzten 1–2 übersetzten Absätze als Stützkontext.
    glossary: Begriffs-Paare, die der Übersetzung vorgegeben werden.
    fmt="translategemma": TranslateGemma erwartet KEINE System-Nachricht und ein
    strukturiertes user-content [{type, source_lang_code, target_lang_code, text}]
    (siehe Chat-Template des Modells); Glossar/Kontext/Hinweis landen im Textfeld.
    """
    parts: list[str] = []
    if glossary:
        lines = "\n".join(f"- {term} = {translation}" for term, translation in glossary)
        parts.append(f"Glossar (bitte konsequent so übersetzen):\n{lines}")
    if context_paragraphs:
        context = "\n\n".join(context_paragraphs[-2:])
        parts.append(
            "Bisherige Übersetzung (nur als Kontext für einen flüssigen Anschluss, "
            f"nicht wiederholen):\n{context}"
        )
    if extra_hint:
        parts.append(extra_hint)
    parts.append(f'Zu übersetzender Text:\n"""\n{source_text}\n"""')
    if fmt == "translategemma":
        body = "\n\n".join(parts)
        return [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "source_lang_code": "en",
                        "target_lang_code": "de",
                        "text": body,
                    }
                ],
            }
        ]
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


# Muster fuer typische Modell-Artefakte am Anfang einer Antwort (Echo des Prompts).
_LEADING_MARKER_RE = re.compile(
    r"^\s*(?:hier ist die [üu]bersetzung|here is the translation|here's the translation|"
    r"[üu]bersetzung|translation|ausgabe|output)\s*:?\s*",
    re.IGNORECASE,
)


def sanitize_translation(text: str) -> str:
    """Entfernt typische Artefakte aus der Modell-Antwort, bevor sie geprueft wird.

    Kleine Modelle (z. B. 7B) echoen gelegentlich Prompt-Bestandteile: Code-Fences,
    eine fuehrende Zeile wie "Translation:", Anfuehrungszeichen um den ganzen Text
    oder Chat-Template-Reste. Diese werden hier abgeschnitten; der eigentliche
    Uebersetzungstext bleibt unveraendert.
    """
    out = text.strip()
    # Code-Fences (``` ... ```) um den gesamten Text entfernen
    fence = re.match(r"^```[a-zA-Z]*\s*\n(.*)\n?```\s*$", out, re.DOTALL)
    if fence:
        out = fence.group(1).strip()
    # Marker-Zeilen, Echo der """-Markierung und umschliessende Anfuehrungszeichen
    # in bis zu drei Durchlaeufen entfernen (Reihenfolge variiert je nach Modell)
    for _ in range(3):
        before = out
        out = _LEADING_MARKER_RE.sub("", out, count=1).strip()
        out = re.sub(r'^"""\s*', "", out)
        out = re.sub(r'\s*"""\s*$', "", out)
        out = out.strip()
        if len(out) >= 2 and out[0] in "\"'“”«»" and out[-1] == out[0]:
            out = out[1:-1].strip()
        if out == before:
            break
    # Chat-Template-Reste und Stop-Marker
    out = re.sub(r"<\|im_start\|>|<\|im_end\|>|<\|endoftext\|>", "", out).strip()
    # uebrige einzelne Fence-Zeilen mitten im Text
    out = re.sub(r"^```[a-zA-Z]*\s*$", "", out, flags=re.MULTILINE).strip()
    # ueberfluessige Leerzeilen kollabieren
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def quality_check(source: str, translated: str) -> str | None:
    """Prüft die Qualität eines übersetzten Abschnitts.

    Returns None bei bestandener Prüfung, sonst eine deutsche Beschreibung
    des Problems (löst einen erneuten Versuch aus).
    """
    src_len = len(source.strip())
    out = translated.strip()
    if not out:
        return "Die Übersetzung ist leer."
    if src_len > 0 and len(out) < src_len * 0.25:
        return "Die Übersetzung ist auffällig kürzer als der Quelltext (weniger als ein Viertel)."
    lowered = out.lower()
    for marker in FORBIDDEN_MARKERS:
        if marker in lowered:
            return f"Die Antwort enthält unerwünschten Text („{marker}“)."
    words = lowered.split()
    if words:
        english = sum(1 for w in words if w.strip(".,;:!?\"'()[]«»") in ENGLISH_STOPWORDS)
        if english / len(words) > MAX_ENGLISH_STOPWORD_RATIO:
            return "Der Text wirkt nicht übersetzt (auffällig viele englische Wörter)."
    return None
