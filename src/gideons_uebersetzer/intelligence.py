"""Intelligente Hilfsfunktionen: Spracherkennung, Hardware-Empfehlung, Glossar-Filterung,
Kapitelüberschriften-Batch und schnelle Dokument-Vorab-Analyse.

Alle Funktionen laufen vollständig lokal ohne Internet und ohne Zusatzabhängigkeiten.
"""

from __future__ import annotations

import ctypes
import os
import platform
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from collections import Counter

from .settings import MODEL_PRESETS

LANGUAGE_NAMES_DE = {
    "de": "Deutsch",
    "en": "Englisch",
    "fr": "Französisch",
    "es": "Spanisch",
    "it": "Italienisch",
}

# Häufige Funktionswörter je Sprache für eine schnelle, robuste Spracherkennung.
_LANG_STOPWORDS: dict[str, set[str]] = {
    "de": {
        "der", "die", "das", "und", "ist", "nicht", "ein", "eine", "einer", "einem", "einen",
        "ich", "sie", "wir", "ihr", "mit", "auf", "für", "von", "zu", "zum", "zur", "den", "dem",
        "des", "sich", "auch", "aber", "oder", "wie", "noch", "nur", "schon", "wenn", "dass",
        "war", "waren", "wird", "werden", "hat", "haben", "hatte", "kann", "können", "über",
        "durch", "nach", "bei", "aus", "als", "mehr", "sehr", "hier", "dort", "dann", "weil",
    },
    "en": {
        "the", "and", "of", "to", "in", "that", "is", "was", "it", "for", "on", "with", "as",
        "at", "by", "an", "be", "this", "which", "or", "from", "but", "not", "are", "were",
        "they", "he", "she", "his", "her", "you", "we", "have", "had", "has", "would", "could",
        "should", "there", "their", "what", "when", "where", "who", "into", "about", "than",
    },
    "fr": {
        "le", "la", "les", "de", "des", "du", "un", "une", "et", "est", "dans", "que", "qui",
        "pour", "pas", "sur", "avec", "plus", "par", "son", "ses", "mais", "nous", "vous",
        "ils", "elles", "elle", "tout", "tous", "comme", "dans", "cette", "ce", "aux", "était",
        "sont", "avait", "être", "avoir", "mais", "aussi", "très", "sans", "sous", "entre",
    },
    "es": {
        "el", "la", "los", "las", "de", "del", "un", "una", "y", "es", "en", "que", "por",
        "para", "con", "no", "una", "su", "sus", "pero", "como", "más", "este", "esta", "estos",
        "había", "era", "son", "fue", "todo", "todos", "muy", "sin", "sobre", "entre", "también",
        "cuando", "donde", "quien", "porque", "desde", "hasta", "ella", "ellos", "nosotros",
    },
    "it": {
        "il", "lo", "la", "i", "gli", "le", "di", "del", "della", "degli", "delle", "un",
        "una", "uno", "e", "ed", "è", "che", "non", "per", "con", "su", "sul", "sulla",
        "come", "ma", "più", "anche", "questo", "questa", "sono", "era", "erano", "aveva",
        "essere", "avere", "tutto", "tutti", "molto", "senza", "tra", "fra", "quando",
        "dove", "perché", "dopo", "prima", "loro", "noi", "voi", "nel", "nella", "alla",
        "alle", "al", "ai", "da", "dal", "dalla", "suoi", "sue", "suo", "sua", "in",
    },
}

_LANG_SPECIAL_CHARS = {
    "de": "äöüßÄÖÜ",
    "fr": "éèêëàâçîïôùûœÉÈÊËÀÂÇ",
    "es": "ñáéíóúü¿¡ÑÁÉÍÓÚ",
    "it": "àèéìòóùÀÈÉÌÒÓÙ",
}

_WORD_RE = re.compile(r"[a-zA-ZäöüÄÖÜßéèêëàâçîïôùûœñáíóú¿¡]+")


def detect_language(text: str) -> str:
    """Erkennt grob die Sprache eines Textes: 'de', 'en', 'fr', 'es', 'it' oder 'unknown'."""
    words = [w.lower() for w in _WORD_RE.findall(text or "")]
    if len(words) < 12:
        return "unknown"
    scores: dict[str, float] = {}
    for lang, sw in _LANG_STOPWORDS.items():
        hits = sum(1 for w in words if w in sw)
        specials = _LANG_SPECIAL_CHARS.get(lang, "")
        bonus = sum(1 for ch in text if ch in specials) * 0.35 if specials else 0.0
        scores[lang] = (hits + bonus) / len(words)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_lang, best_score = ranked[0]
    second_score = ranked[1][1]
    if best_score >= 0.08 and best_score >= second_score * 1.25:
        return best_lang
    return "unknown"


def is_likely_german(text: str) -> bool:
    """True, wenn der Text klar überwiegend deutsch wirkt."""
    return detect_language(text) == "de"


def resolve_source_language(setting_lang: str, sample_text: str) -> str:
    """Bestimmt die effektive Ausgangssprache ('en', 'fr', 'es', 'it').

    Bei setting_lang='auto' wird die Sprache automatisch erkannt; bei 'unknown' oder 'de'
    wird sicher auf 'en' zurückgefallen.
    """
    if setting_lang in ("en", "fr", "es", "it"):
        return setting_lang
    detected = detect_language(sample_text)
    if detected in ("en", "fr", "es", "it"):
        return detected
    return "en"


# Häufige großgeschriebene Wörter, die keine Eigennamen für das Auto-Glossar sind.
_AUTO_GLOSSARY_IGNORE = {
    "the", "and", "but", "for", "with", "from", "that", "this", "these", "those", "there",
    "their", "they", "them", "then", "than", "when", "where", "which", "while", "what",
    "who", "whom", "whose", "into", "onto", "over", "under", "after", "before", "between",
    "through", "during", "without", "within", "chapter", "part", "section", "page", "book",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august", "september",
    "october", "november", "december", "mr", "mrs", "ms", "dr", "prof", "sir", "lord", "lady",
    "les", "des", "une", "pour", "avec", "dans", "mais", "plus", "sans", "tout", "cette",
    "los", "las", "del", "una", "por", "para", "con", "pero", "como", "todo", "esta",
    "gli", "del", "della", "che", "non", "per", "come", "questo", "questa", "tutto",
}

# Erkennt 1- bis 3-teilige Eigennamen/Begriffe mitten im Satz (nach Kleinbuchstabe/Komma/Leerzeichen).
_MID_SENTENCE_ENTITY_RE = re.compile(
    r"(?<=[a-zäöüßéèêàçñ,;:\(\s])\s+([A-ZÄÖÜÉÈÊÀÇÑ][a-zäöüßéèêàçñ]{2,}(?:\s+[A-ZÄÖÜÉÈÊÀÇÑ][a-zäöüßéèêàçñ]{2,}){0,2})"
)


def extract_auto_glossary(
    texts: list[str],
    min_occurrences: int = 3,
    max_entries: int = 25,
) -> list[tuple[str, str]]:
    """Extrahiert wiederkehrende Eigennamen/Orte aus dem Buch für konsistente Übersetzung.

    Findet großgeschriebene Begriffe (1–3 Wörter), die wiederholt mitten im Satz auftreten,
    damit Namen wie 'Sherlock Holmes' oder 'Baker Street' über das ganze Buch einheitlich
    beibehalten und nicht versehentlich eingedeutscht werden.
    """
    counts: Counter[str] = Counter()
    for text in texts:
        for match in _MID_SENTENCE_ENTITY_RE.finditer(text or ""):
            term = match.group(1).strip()
            parts = term.split()
            if all(p.lower() in _AUTO_GLOSSARY_IGNORE for p in parts):
                continue
            if parts[0].lower() in _AUTO_GLOSSARY_IGNORE:
                continue
            counts[term] += 1

    # Längere Mehrwort-Begriffe bevorzugen (z. B. "Sherlock Holmes" statt nur "Sherlock")
    candidates = [(term, cnt) for term, cnt in counts.items() if cnt >= min_occurrences]
    candidates.sort(key=lambda item: (len(item[0].split()) > 1, item[1], len(item[0])), reverse=True)

    chosen: list[str] = []
    for term, _cnt in candidates:
        if len(chosen) >= max_entries:
            break
        # Einzelwort überspringen, wenn es bereits Teil eines gewählten Mehrwort-Namens ist
        if len(term.split()) == 1 and any(term in multi.split() for multi in chosen if " " in multi):
            continue
        chosen.append(term)
    return [(term, term) for term in chosen]


def merge_glossaries(
    user_glossary: list[tuple[str, str]],
    auto_glossary: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Führt Nutzer-Glossar und Auto-Glossar zusammen (Nutzer-Einträge haben immer Vorrang)."""
    merged = list(user_glossary)
    seen = {term.lower() for term, _ in user_glossary}
    for term, translation in auto_glossary:
        if term.lower() not in seen:
            merged.append((term, translation))
            seen.add(term.lower())
    return merged


def detect_system_ram_gb() -> float | None:
    """Ermittelt den installierten Arbeitsspeicher in GiB (plattformübergreifend, ohne psutil)."""
    sys_name = platform.system()
    if sys_name == "Windows":
        try:
            class _MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = _MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return stat.ullTotalPhys / (1024 ** 3)
        except Exception:
            return None
    if sys_name == "Linux":
        try:
            for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return kb / (1024 ** 2)
        except Exception:
            return None
    if sys_name == "Darwin":
        try:
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True, timeout=2).strip()
            return int(out) / (1024 ** 3)
        except Exception:
            return None
    return None


@dataclass
class ModelRecommendation:
    preset_id: str
    preset_index: int
    ram_gb: float | None
    has_gpu: bool
    reason: str


def recommend_model_preset(ram_gb: float | None = None, has_gpu: bool | None = None) -> ModelRecommendation:
    """Empfiehlt anhand von RAM und GPU das passendste lokale Übersetzungsmodell."""
    if ram_gb is None:
        ram_gb = detect_system_ram_gb()
    if has_gpu is None:
        try:
            from .translator_local import cuda_available

            has_gpu = cuda_available()
        except Exception:
            has_gpu = False

    if ram_gb is not None and ram_gb < 8.5:
        preset_id = "translategemma-4b"
        reason = (
            f"Erkannt: ca. {ram_gb:.0f} GB RAM – kompaktes Modell TranslateGemma-4B-IT (2,3 GB) "
            "läuft flüssig ohne Speicherengpass."
        )
    elif (ram_gb is not None and ram_gb >= 15.5) and has_gpu:
        preset_id = "translategemma-12b"
        reason = (
            f"Erkannt: ca. {ram_gb:.0f} GB RAM + NVIDIA-GPU – spezialisiertes Modell "
            "TranslateGemma-12B-IT (6,8 GB) liefert die höchste Übersetzungsqualität."
        )
    else:
        preset_id = "qwen2.5-7b"
        ram_txt = f"ca. {ram_gb:.0f} GB RAM" if ram_gb is not None else "Standard-System"
        gpu_txt = " + NVIDIA-GPU" if has_gpu else " (CPU-Betrieb)"
        reason = (
            f"Erkannt: {ram_txt}{gpu_txt} – Qwen2.5-7B-Instruct (4,7 GB) bietet das beste "
            "Verhältnis aus Qualität und Geschwindigkeit."
        )

    idx = next((i for i, p in enumerate(MODEL_PRESETS) if p["id"] == preset_id), 0)
    return ModelRecommendation(
        preset_id=preset_id,
        preset_index=idx,
        ram_gb=ram_gb,
        has_gpu=bool(has_gpu),
        reason=reason,
    )


def filter_relevant_glossary(
    glossary: list[tuple[str, str]],
    source_text: str,
    always_keep_limit: int = 10,
) -> list[tuple[str, str]]:
    """Filtert große Glossare auf Einträge, deren Ausgangsbegriff im Quelltext vorkommt.

    Bei kleinen Glossaren (<= always_keep_limit) werden alle Einträge unverändert behalten.
    """
    if not glossary or len(glossary) <= always_keep_limit:
        return list(glossary)
    lowered = source_text.lower()
    relevant: list[tuple[str, str]] = []
    for term, translation in glossary:
        t_low = term.lower().strip()
        if not t_low:
            continue
        # Schneller Substring-Vorfilter, dann Wortgrenzen-Check bei alphanumerischen Begriffen
        if t_low in lowered:
            if re.search(rf"(?<!\w){re.escape(t_low)}(?!\w)", lowered):
                relevant.append((term, translation))
    return relevant


def build_headings_block(titles: list[str]) -> str:
    """Formatiert eine Liste von Kapitelüberschriften als nummerierten Block zum Übersetzen."""
    lines = [f"[{i + 1}] {t.strip()}" for i, t in enumerate(titles)]
    return "\n".join(lines)


def parse_translated_headings(translated_block: str, expected_count: int) -> dict[int, str]:
    """Parst nummerierte übersetzte Kapitelüberschriften ('[1] Kapitel 1') -> {0: 'Kapitel 1'}."""
    result: dict[int, str] = {}
    for line in (translated_block or "").splitlines():
        m = re.match(r"^\s*\[?(\d+)\]?[\.\):\-]?\s+(.+?)\s*$", line)
        if not m:
            continue
        idx = int(m.group(1)) - 1
        title = m.group(2).strip().strip('"\'«»„“')
        if 0 <= idx < expected_count and title:
            result[idx] = title
    return result


@dataclass
class QueueSummary:
    file_count: int
    total_bytes: int
    cached_count: int
    missing_count: int


def summarize_queue(paths: list[Path], cache_loader=None) -> QueueSummary:
    """Erstellt eine schnelle Übersicht über die aktuelle Warteschlange."""
    total_bytes = 0
    cached = 0
    missing = 0
    for p in paths:
        if not p.is_file():
            missing += 1
            continue
        try:
            total_bytes += p.stat().st_size
        except OSError:
            pass
        if cache_loader is not None:
            try:
                if cache_loader(p) is not None:
                    cached += 1
            except Exception:
                pass
    return QueueSummary(
        file_count=len(paths),
        total_bytes=total_bytes,
        cached_count=cached,
        missing_count=missing,
    )
