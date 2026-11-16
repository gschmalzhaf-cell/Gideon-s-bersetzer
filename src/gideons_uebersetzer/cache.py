"""Lokaler Zwischenspeicher für Übersetzungen (JSON je PDF).

Übersetzte Abschnitte werden laufend gesichert, damit eine abgebrochene
Übersetzung später mit einem Klick fortgesetzt werden kann.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from .settings import cache_dir

STATUS_DONE = "done"
STATUS_FAILED = "failed"


@dataclass
class CachedChunk:
    index: int
    text: str
    translation: str
    status: str  # STATUS_DONE oder STATUS_FAILED
    problem: str = ""  # bei STATUS_FAILED: Grund der Qualitätsprüfung


class TranslationCache:
    """JSON-Zwischenspeicher für genau ein Quell-PDF."""

    def __init__(self, source_path: Path, cache_file: Path, chunks: list[CachedChunk] | None = None,
                 tool: str = "", created_at: float = 0.0):
        self.source_path = Path(source_path)
        self.cache_file = Path(cache_file)
        self.tool = tool
        self.created_at = created_at or time.time()
        self.chunks: dict[int, CachedChunk] = {c.index: c for c in (chunks or [])}

    @staticmethod
    def cache_file_for(source_path: str | Path, base_dir: Path | None = None) -> Path:
        """Eindeutige Cache-Datei für ein PDF (basierend auf Pfad, Größe, Änderungszeit)."""
        source_path = Path(source_path).resolve()
        stat = source_path.stat()
        key = f"{source_path}|{stat.st_size}|{int(stat.st_mtime)}"
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
        base = base_dir or cache_dir()
        return base / f"{digest}.json"

    @classmethod
    def load(cls, source_path: str | Path, base_dir: Path | None = None) -> "TranslationCache | None":
        """Lädt einen vorhandenen Zwischenspeicher, sonst None."""
        cache_file = cls.cache_file_for(source_path, base_dir)
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        chunks = [
            CachedChunk(
                index=int(c["index"]),
                text=c.get("text", ""),
                translation=c.get("translation", ""),
                status=c.get("status", STATUS_DONE),
                problem=c.get("problem", ""),
            )
            for c in data.get("chunks", [])
        ]
        return cls(
            source_path=Path(data.get("source_path", str(source_path))),
            cache_file=cache_file,
            chunks=chunks,
            tool=data.get("tool", ""),
            created_at=float(data.get("created_at", 0.0)),
        )

    def matches(self, chunk_texts: list[str]) -> bool:
        """Prüft, ob der Zwischenspeicher zum aktuellen Dokument passt."""
        if len(self.chunks) != len(chunk_texts):
            return False
        return all(
            index in self.chunks and self.chunks[index].text == text
            for index, text in enumerate(chunk_texts)
        )

    def get(self, index: int) -> CachedChunk | None:
        return self.chunks.get(index)

    def record(self, index: int, source_text: str, translation: str, status: str, problem: str = "") -> None:
        self.chunks[index] = CachedChunk(
            index=index, text=source_text, translation=translation, status=status, problem=problem
        )
        self.save()

    def save(self) -> None:
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "source_path": str(self.source_path),
            "tool": self.tool,
            "created_at": self.created_at,
            "chunks": [
                {"index": c.index, "text": c.text, "translation": c.translation, "status": c.status, "problem": c.problem}
                for c in sorted(self.chunks.values(), key=lambda c: c.index)
            ],
        }
        tmp = self.cache_file.with_suffix(self.cache_file.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.cache_file)

    def clear(self) -> None:
        try:
            self.cache_file.unlink()
        except OSError:
            pass
        self.chunks.clear()

    @property
    def done_count(self) -> int:
        return sum(1 for c in self.chunks.values() if c.status == STATUS_DONE)

    @property
    def failed_count(self) -> int:
        return sum(1 for c in self.chunks.values() if c.status == STATUS_FAILED)
