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

_SOURCE_LANG_ADJECTIVE = {
    "en": "englischen",
    "fr": "französischen",
    "es": "spanischen",
    "it": "italienischen",
}

_STYLE_INSTRUCTIONS = {
    "literary": (
        "Du bist ein professioneller Literaturübersetzer. Übersetze den folgenden "
        "{lang_adj} Text flüssig, stilvoll und natürlich klingend ins Deutsche "
        "(authentische Dialoge, literarischer Erzählton)."
    ),
    "nonfiction": (
        "Du bist ein professioneller Sachbuch-Übersetzer. Übersetze den folgenden "
        "{lang_adj} Text klar, präzise und gut verständlich ins Deutsche "
        "(sachlicher, strukturierter Stil)."
    ),
    "technical": (
        "Du bist ein professioneller Fachübersetzer für Technik und Wissenschaft. "
        "Übersetze den folgenden {lang_adj} Text exakt und terminologisch konsistent ins Deutsche; "
        "etablierte Fachbegriffe, Code-Bezeichner und Produktnamen bleiben unverändert."
    ),
}

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

# Eindeutige Stoppwörter je Ausgangssprache (ohne deutsch-identische Wörter wie "in", "an", "was", "des").
ENGLISH_STOPWORDS = {
    "the", "and", "of", "to", "that", "is", "it", "for", "on", "with",
    "as", "at", "by", "be", "this", "which", "or", "from", "but", "not",
    "are", "were", "they", "he", "she", "his", "her", "you", "we",
}
SOURCE_STOPWORDS = {
    "en": ENGLISH_STOPWORDS,
    "fr": {"le", "la", "les", "une", "est", "dans", "que", "qui", "pour", "pas", "avec", "plus", "mais", "nous", "vous", "cette", "était"},
    "es": {"el", "los", "las", "del", "una", "por", "para", "con", "pero", "como", "más", "este", "esta", "había", "todo", "muy", "porque"},
    "it": {"il", "lo", "gli", "della", "una", "che", "non", "per", "con", "come", "più", "anche", "questo", "questa", "sono", "era", "molto"},
}
GERMAN_STOPWORDS = {
    "der", "die", "das", "und", "ist", "nicht", "ein", "eine", "einer", "einem", "einen",
    "ich", "sie", "wir", "ihr", "mit", "auf", "für", "von", "zu", "zum", "zur", "den", "dem",
    "des", "sich", "auch", "aber", "oder", "wie", "noch", "nur", "schon", "wenn", "dass",
    "war", "waren", "wird", "werden", "hat", "haben", "hatte", "kann", "können", "über",
    "durch", "nach", "bei", "aus", "als", "bitte", "an", "in", "was", "diesem", "kapitel",
}
MAX_ENGLISH_STOPWORD_RATIO = 0.08
MIN_FOREIGN_STOPWORDS = 3


def build_system_prompt(style_profile: str = "literary", source_lang: str = "en") -> str:
    """Erzeugt den System-Prompt passend zu Stil-Profil und Ausgangssprache."""
    lang_adj = _SOURCE_LANG_ADJECTIVE.get(source_lang, "englischen")
    intro = _STYLE_INSTRUCTIONS.get(style_profile, _STYLE_INSTRUCTIONS["literary"]).format(lang_adj=lang_adj)
    return (
        f"{intro} Antworte ausschließlich mit der Übersetzung: "
        "keine Einleitung, kein Kommentar, keine Anführungszeichen um den gesamten "
        "Text, keine Erklärungen. Behalte die Absatzstruktur des Originals bei."
    )


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


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…»\"'])\s+(?=[A-ZÄÖÜ\"'«„(])")


def _split_long_paragraph(text: str, max_words: int) -> list[str]:
    """Teilt einen überlangen Absatz intelligent an Satzgrenzen (nie mitten im Satz)."""
    if len(text.split()) <= max_words:
        return [text]
    sentences = _SENTENCE_SPLIT_RE.split(text.strip())
    if len(sentences) <= 1:
        return [text]
    parts: list[str] = []
    buf: list[str] = []
    buf_words = 0
    for sent in sentences:
        sw = len(sent.split())
        if buf and buf_words + sw > max_words:
            parts.append(" ".join(buf))
            buf = [sent]
            buf_words = sw
        else:
            buf.append(sent)
            buf_words += sw
    if buf:
        parts.append(" ".join(buf))
    return parts


def split_into_chunks(chapters: list[Chapter], chunk_words: int) -> list[Chunk]:
    """Gruppiert Absätze zu Abschnitten von etwa chunk_words Wörtern.

    Absätze werden nicht mitten im Satz geteilt (überlange Einzelabsätze werden
    intelligent an Satzgrenzen zerlegt) und Kapitelgrenzen werden nie überschritten.
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
            for piece in _split_long_paragraph(paragraph.text, chunk_words):
                words = len(piece.split())
                if current_paragraphs and current_words + words > chunk_words:
                    flush()
                    current_page = paragraph.page
                current_paragraphs.append(piece)
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
    """"translategemma", wenn das gewählte Modell TranslateGemma ist (eigenes Prompt-Format).

    Nur im Offline-Betrieb (tool="offline"): llama.cpp wendet das Chat-Template des
    GGUF-Modells an und TranslateGemma erwartet das strukturierte user-content
    (Liste mit source_lang_code/target_lang_code). Im API-Betrieb (Mistral) muss
    content dagegen ein einfacher String sein – das strukturierte Format wird mit
    HTTP 422 abgelehnt ("Input should be a valid string").
    """
    if getattr(settings, "tool", "offline") != "offline":
        return "default"
    haystack = f"{settings.hf_filename} {settings.model_path}".lower()
    return "translategemma" if "translategemma" in haystack else "default"


def build_messages(
    source_text: str,
    context_paragraphs: list[str],
    glossary: list[tuple[str, str]],
    extra_hint: str = "",
    fmt: str = "default",
    style_profile: str = "literary",
    source_lang: str = "en",
) -> list[dict]:
    """Baut die Chat-Nachrichten für einen Übersetzungsaufruf.

    context_paragraphs: die letzten 1–2 übersetzten Absätze als Stützkontext.
    glossary: Begriffs-Paare, die der Übersetzung vorgegeben werden.
    fmt="translategemma": TranslateGemma erwartet KEINE System-Nachricht und ein
    strukturiertes user-content [{type, source_lang_code, target_lang_code, text}]
    (siehe Chat-Template des Modells); Glossar/Kontext/Hinweis landen im Textfeld.
    """
    src_code = source_lang if source_lang in ("en", "fr", "es", "it") else "en"
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
    if fmt == "translategemma" and style_profile in ("nonfiction", "technical"):
        style_note = (
            "Stil: Sachbuch (klar, präzise, sachlich)."
            if style_profile == "nonfiction"
            else "Stil: Fachbuch/Technik (exakt, etablierte Fachbegriffe beibehalten)."
        )
        parts.append(style_note)
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
                        "source_lang_code": src_code,
                        "target_lang_code": "de",
                        "text": body,
                    }
                ],
            }
        ]
    return [
        {"role": "system", "content": build_system_prompt(style_profile, src_code)},
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


def quality_check(source: str, translated: str, source_lang: str = "en") -> str | None:
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
    if src_len >= 120 and len(out) > max(src_len * 3.5, 600):
        return "Die Übersetzung ist auffällig länger als der Quelltext (möglicherweise Halluzination oder Wiederholung)."
    lowered = out.lower()
    for marker in FORBIDDEN_MARKERS:
        if marker in lowered:
            return f"Die Antwort enthält unerwünschten Text („{marker}“)."
    words = [w.strip(".,;:!?\"'()[]«»„“") for w in lowered.split()]
    words = [w for w in words if w]
    if words:
        stopwords = SOURCE_STOPWORDS.get(source_lang, ENGLISH_STOPWORDS)
        foreign = sum(1 for w in words if w in stopwords)
        german = sum(1 for w in words if w in GERMAN_STOPWORDS)
        if (
            foreign >= MIN_FOREIGN_STOPWORDS
            and foreign / len(words) > MAX_ENGLISH_STOPWORD_RATIO
            and foreign > german
        ):
            return "Der Text wirkt nicht übersetzt (auffällig viele Wörter der Ausgangssprache)."
    return None
