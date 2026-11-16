"""Diagnose-Report für Fehleranalyse und Qualitätsverbesserung.

Ein Report ist eine einzelne Markdown-Datei mit Klartext-Abschnitten und einem
JSON-Anhang (maschinenlesbar). Der API-Schlüssel wird NIE aufgenommen (redigiert);
von fehlgeschlagenen Abschnitten nur ein kurzer Quelltext-Ausschnitt (max. 300 Zeichen),
damit keine Buchinhalte im Report landen.
"""

from __future__ import annotations

import json
import platform
import sys
from datetime import datetime
from pathlib import Path

from . import __version__, model_manager
from .cache import STATUS_DONE, STATUS_FAILED
from .settings import Settings, cache_dir, models_dir

LOG_BUFFER: list[str] = []
LOG_BUFFER_MAX = 500


def add_log_line(line: str) -> None:
    """Hängt eine Log-Zeile an den Ringpuffer für den Report an."""
    LOG_BUFFER.append(line)
    if len(LOG_BUFFER) > LOG_BUFFER_MAX:
        del LOG_BUFFER[: len(LOG_BUFFER) - LOG_BUFFER_MAX]


def _redacted_settings(settings: Settings) -> dict:
    data = settings.to_dict()
    if data.get("api_key"):
        data["api_key"] = "***"
    return data


def _cache_summaries() -> list[dict]:
    summaries: list[dict] = []
    try:
        cache_files = sorted(cache_dir().glob("*.json"))
    except OSError:
        cache_files = []
    for cache_file in cache_files:
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        chunks = data.get("chunks", [])
        failed = [
            {
                "index": c.get("index"),
                "problem": c.get("problem", ""),
                "source_excerpt": (c.get("text", "") or "")[:300],
            }
            for c in chunks
            if c.get("status") == STATUS_FAILED
        ]
        summaries.append(
            {
                "file": cache_file.name,
                "source_path": data.get("source_path", ""),
                "tool": data.get("tool", ""),
                "done": sum(1 for c in chunks if c.get("status") == STATUS_DONE),
                "failed": len(failed),
                "failed_chunks": failed,
            }
        )
    return summaries


def build_report(settings: Settings, log_lines: list[str] | None = None) -> str:
    """Baut den Report als Markdown-Text (mit JSON-Anhang)."""
    model_path = settings.resolved_model_path()
    lines = log_lines if log_lines is not None else list(LOG_BUFFER)
    caches = _cache_summaries()
    now = datetime.now().isoformat(timespec="seconds")
    present = model_manager.is_model_present(model_path)

    md: list[str] = []
    md.append("# Gideon's Übersetzer – Diagnose-Report")
    md.append("")
    md.append(f"- Erstellt am: {now}")
    md.append(f"- App-Version: {__version__}")
    md.append(f"- Python: {platform.python_version()} ({sys.platform})")
    md.append(f"- Betriebssystem: {platform.platform()}")
    md.append("")
    md.append("## Einstellungen (API-Schlüssel redigiert)")
    md.append("")
    md.append("```json")
    md.append(json.dumps(_redacted_settings(settings), ensure_ascii=False, indent=2))
    md.append("```")
    md.append("")
    md.append("## Modell")
    md.append("")
    md.append(f"- HF-Repo/Datei: `{settings.hf_repo}/{settings.hf_filename}`")
    md.append(f"- Modellpfad: `{model_path}`")
    size = f" ({model_manager.format_bytes(model_manager.model_disk_usage(model_path))})" if present else ""
    md.append(f"- Lokal vorhanden: {'ja' if present else 'nein'}{size}")
    try:
        free = model_manager.free_space_bytes(models_dir() if models_dir().exists() else Path.home())
        md.append(f"- Freier Speicher: {model_manager.format_bytes(free)}")
    except OSError:
        pass
    md.append(
        f"- OCR: enabled={settings.ocr_enabled}, backend={settings.ocr_backend}, "
        f"effektiv={settings.effective_ocr_backend(settings.tool, settings.online_enabled)}"
    )
    md.append("")
    md.append("## Zwischenspeicher (abgebrochene/fehlgeschlagene Übersetzungen)")
    md.append("")
    if not caches:
        md.append("_Keine Zwischenspeicher vorhanden._")
    for c in caches:
        md.append(
            f"### {c['source_path'] or c['file']} (tool={c['tool'] or '?'}): "
            f"{c['done']} ok, {c['failed']} fehlgeschlagen"
        )
        for f in c["failed_chunks"]:
            md.append(f"- Abschnitt {f['index'] + 1}: {f['problem']}")
            md.append(f"  Quelltext (erste 300 Zeichen): {f['source_excerpt']!r}")
        md.append("")
    md.append("## Log (letzte Zeilen)")
    md.append("")
    md.append("```")
    md.extend(lines[-100:] or ["_leer_"])
    md.append("```")
    md.append("")
    md.append("## Maschinenlesbarer Anhang (JSON)")
    md.append("")
    md.append("```json")
    md.append(
        json.dumps(
            {
                "version": __version__,
                "created_at": now,
                "platform": platform.platform(),
                "python": platform.python_version(),
                "settings": _redacted_settings(settings),
                "model": {
                    "repo": settings.hf_repo,
                    "filename": settings.hf_filename,
                    "path": str(model_path),
                    "present": present,
                },
                "caches": caches,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    md.append("```")
    md.append("")
    return "\n".join(md)


def write_report(settings: Settings, out_path: Path | None = None) -> Path:
    """Schreibt den Report als Markdown-Datei und liefert den Pfad."""
    if out_path is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_path = settings.resolved_output_dir() / f"Gideons-Uebersetzer-Report-{stamp}.md"
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_report(settings), encoding="utf-8")
    return out_path
