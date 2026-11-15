"""Einstellungen der Anwendung.

Die Einstellungen werden als JSON-Datei im Benutzerprofil abgelegt
(Windows: %LOCALAPPDATA%\\Tolino-Uebersetzer\\settings.json) und beim Start
automatisch geladen. Fehlende Felder werden mit Standardwerten aufgefüllt.
"""

from __future__ import annotations

import json
import os
import platform
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

DEFAULT_API_ENDPOINT = "https://api.mistral.ai/v1/chat/completions"
DEFAULT_API_MODEL = "mistral-small-latest"
DEFAULT_HF_REPO = "bartowski/Mistral-7B-Instruct-v0.3-GGUF"
DEFAULT_HF_FILENAME = "Mistral-7B-Instruct-v0.3.Q4_K_M.gguf"
DEFAULT_CHUNK_WORDS = 1500
DEFAULT_TEMPERATURE = 0.3


def app_data_dir() -> Path:
    """Gibt das Konfigurationsverzeichnis im Benutzerprofil zurück."""
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / "Tolino-Uebersetzer"
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Tolino-Uebersetzer"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "Tolino-Uebersetzer"


def models_dir() -> Path:
    """Ablageordner für das Offline-Modell (%LOCALAPPDATA%\\Tolino-Uebersetzer\\models)."""
    return app_data_dir() / "models"


def cache_dir() -> Path:
    """Ablageordner für die JSON-Zwischenspeicher der Übersetzungen."""
    return app_data_dir() / "cache"


def default_settings_path() -> Path:
    return app_data_dir() / "settings.json"


def default_output_dir() -> Path:
    home = Path.home()
    docs = home / "Documents"
    return docs if docs.is_dir() else home


def default_model_path() -> Path:
    return models_dir() / DEFAULT_HF_FILENAME


@dataclass
class Settings:
    """Alle persistierten Einstellungen."""

    tool: str = "offline"  # "offline" oder "api"
    online_enabled: bool = False  # Online-Betrieb nur nach bewusstem Einschalten
    api_key: str = ""
    api_model: str = DEFAULT_API_MODEL
    api_endpoint: str = DEFAULT_API_ENDPOINT
    temperature: float = DEFAULT_TEMPERATURE
    chunk_size: int = DEFAULT_CHUNK_WORDS  # Wörter pro Übersetzungsabschnitt
    glossary_path: str = ""
    model_path: str = ""  # leer = Standardpfad unter models_dir()
    hf_repo: str = DEFAULT_HF_REPO
    hf_filename: str = DEFAULT_HF_FILENAME
    output_dir: str = ""  # leer = Standard-Zielordner
    ocr_enabled: bool = True  # gescannte PDF-Seiten per OCR erkennen
    first_start_done: bool = False

    def resolved_model_path(self) -> Path:
        return Path(self.model_path) if self.model_path else default_model_path()

    def resolved_output_dir(self) -> Path:
        return Path(self.output_dir) if self.output_dir else default_output_dir()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        known = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in known}
        return cls(**kwargs)


def load_settings(path: Path | None = None) -> Settings:
    """Lädt die Einstellungen; bei fehlender oder ungültiger Datei Standardwerte."""
    path = path or default_settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return Settings.from_dict(data)
    except (OSError, ValueError):
        pass
    return Settings()


def save_settings(settings: Settings, path: Path | None = None) -> Path:
    """Speichert die Einstellungen atomar (erst temporäre Datei, dann Umbenennen)."""
    path = path or default_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(settings.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    return path
