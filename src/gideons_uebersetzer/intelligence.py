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

from .settings import MODEL_PRESETS

# Häufige deutsche und englische Funktionswörter für eine schnelle, robuste Spracherkennung.
_DE_STOPWORDS = {
    "der", "die", "das", "und", "ist", "nicht", "ein", "eine", "einer", "einem", "einen",
    "ich", "sie", "wir", "ihr", "mit", "auf", "für", "von", "zu", "zum", "zur", "den", "dem",
    "des", "sich", "auch", "aber", "oder", "wie", "noch", "nur", "schon", "wenn", "dass",
    "war", "waren", "wird", "werden", "hat", "haben", "hatte", "kann", "können", "über",
    "durch", "nach", "bei", "aus", "als", "mehr", "sehr", "hier", "dort", "dann", "weil",
}
_EN_STOPWORDS = {
    "the", "and", "of", "to", "in", "that", "is", "was", "it", "for", "on", "with", "as",
    "at", "by", "an", "be", "this", "which", "or", "from", "but", "not", "are", "were",
    "they", "he", "she", "his", "her", "you", "we", "have", "had", "has", "would", "could",
    "should", "there", "their", "what", "when", "where", "who", "into", "about", "than",
}

_WORD_RE = re.compile(r"[a-zA-ZäöüÄÖÜß]+")


def detect_language(text: str) -> str:
    """Erkennt grob die Sprache eines Textes: 'de', 'en' oder 'unknown'."""
    words = [w.lower() for w in _WORD_RE.findall(text or "")]
    if len(words) < 12:
        return "unknown"
    de_hits = sum(1 for w in words if w in _DE_STOPWORDS)
    en_hits = sum(1 for w in words if w in _EN_STOPWORDS)
    # Umlaute / ß sind ein starkes Indiz für Deutsch
    umlaut_bonus = sum(1 for ch in text if ch in "äöüßÄÖÜ") * 0.5
    de_score = (de_hits + umlaut_bonus) / len(words)
    en_score = en_hits / len(words)
    if de_score >= 0.08 and de_score > en_score * 1.6:
        return "de"
    if en_score >= 0.08 and en_score > de_score * 1.4:
        return "en"
    return "unknown"


def is_likely_german(text: str) -> bool:
    """True, wenn der Text klar überwiegend deutsch wirkt."""
    return detect_language(text) == "de"


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
