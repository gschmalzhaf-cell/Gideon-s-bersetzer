"""Verwaltung des Offline-Modells: Herunterladen (mit Fortschritt, Abbruch,
Fortsetzen), Prüfen, Löschen und Speicheranzeige.

Das Modell wird einmalig von Hugging Face geladen und liegt danach unter
%LOCALAPPDATA%\\Tolino-Uebersetzer\\models. Der Download benutzt eine
partielle Datei („.part“), die bei Abbruch behalten und später fortgesetzt
wird; fertige Dateien werden vor der Verwendung auf Vollständigkeit geprüft.
"""

from __future__ import annotations

import os
import shutil
import threading
import time
from pathlib import Path
from typing import Callable

import requests
from huggingface_hub import get_hf_file_metadata, hf_hub_url

CHUNK_BYTES = 1024 * 1024  # 1 MiB


class DownloadCancelled(Exception):
    """Der Anwender hat den Modell-Download abgebrochen."""


class ModelError(Exception):
    """Fehler bei der Modellverwaltung mit deutscher Meldung."""


ProgressCallback = Callable[[int, int, float], None]  # (bytes_jetzt, bytes_gesamt, tempo_bytes_pro_sek)


def model_file_info(repo_id: str, filename: str) -> dict:
    """Liefert Größe und URL der Modell-Datei bei Hugging Face."""
    url = hf_hub_url(repo_id=repo_id, filename=filename)
    try:
        meta = get_hf_file_metadata(url)
    except Exception as exc:
        raise ModelError(
            f"Die Modell-Datei „{filename}“ wurde im Repository „{repo_id}“ nicht gefunden ({exc})."
        ) from exc
    size = meta.size or 0
    if not size:
        raise ModelError("Die Dateigröße des Modells konnte nicht ermittelt werden.")
    return {"url": url, "size": int(size), "etag": meta.etag or ""}


def free_space_bytes(path: Path) -> int:
    """Freier Speicherplatz des Laufwerks, auf dem path liegt."""
    return shutil.disk_usage(path).free


def format_bytes(n: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(n) < 1024 or unit == "TiB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TiB"


def download_model(
    repo_id: str,
    filename: str,
    dest_dir: Path,
    progress_cb: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
    resume: bool = True,
) -> Path:
    """Lädt das Modell herunter.

    - Prüft vorher den freien Speicherplatz.
    - Meldet Fortschritt, Geschwindigkeit und Restzeit über progress_cb.
    - Kann jederzeit abgebrochen werden (partielle Datei bleibt für Fortsetzung erhalten).
    - Setzt einen abgebrochenen Download per Range-Request fort.
    - Die fertige Datei wird auf Vollständigkeit geprüft; halbe Dateien werden nie verwendet.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    part = dest_dir / (filename + ".part")

    if dest.is_file():
        return dest

    info = model_file_info(repo_id, filename)
    total = info["size"]

    free = free_space_bytes(dest_dir)
    if free < total + 512 * 1024 * 1024:
        raise ModelError(
            "Auf dem Laufwerk ist nicht genug Speicherplatz frei. "
            f"Benötigt werden ca. {format_bytes(total)}, frei sind {format_bytes(free)}."
        )

    downloaded = 0
    if resume and part.is_file():
        downloaded = part.stat().st_size
        if downloaded >= total:
            os.replace(part, dest)
            return dest

    headers = {"User-Agent": "Gideons-Uebersetzer/1.0"}
    if downloaded > 0:
        headers["Range"] = f"bytes={downloaded}-"

    try:
        response = requests.get(info["url"], headers=headers, stream=True, timeout=(15, 60))
    except requests.RequestException as exc:
        raise ModelError(f"Der Modell-Download konnte nicht gestartet werden: {exc}") from exc

    if response.status_code == 416 or (response.status_code == 200 and downloaded > 0):
        # Server ignoriert Range oder Datei ist schon komplett: sauber neu starten.
        response.close()
        try:
            part.unlink()
        except OSError:
            pass
        downloaded = 0
        response = requests.get(info["url"], headers={"User-Agent": "Gideons-Uebersetzer/1.0"},
                                stream=True, timeout=(15, 60))

    if response.status_code not in (200, 206):
        response.close()
        raise ModelError(f"Hugging Face hat den Download abgelehnt (HTTP {response.status_code}).")

    if response.status_code == 200:
        downloaded = 0

    start_time = time.monotonic()
    last_time = start_time
    last_bytes = downloaded
    speed = 0.0
    try:
        with open(part, "ab") as fh:
            for block in response.iter_content(chunk_size=CHUNK_BYTES):
                if cancel_event is not None and cancel_event.is_set():
                    raise DownloadCancelled("Download abgebrochen.")
                if not block:
                    continue
                fh.write(block)
                downloaded += len(block)
                now = time.monotonic()
                if now - last_time >= 0.5:
                    instant = (downloaded - last_bytes) / (now - last_time)
                    speed = 0.7 * speed + 0.3 * instant if speed else instant
                    last_time, last_bytes = now, downloaded
                    if progress_cb is not None:
                        progress_cb(downloaded, total, speed)
    except requests.RequestException as exc:
        raise ModelError(f"Der Modell-Download wurde unterbrochen: {exc}") from exc
    finally:
        response.close()

    if downloaded < total:
        raise ModelError(
            "Der Modell-Download war unvollständig. Bitte erneut starten – "
            "der Fortschritt wird automatisch fortgesetzt."
        )
    os.replace(part, dest)
    if progress_cb is not None:
        progress_cb(downloaded, total, speed)
    return dest


def delete_model(model_path: str | Path) -> int:
    """Löscht das Modell (und ggf. eine partielle Datei). Liefert freigegebene Bytes."""
    model_path = Path(model_path)
    freed = 0
    for candidate in (model_path, model_path.with_name(model_path.name + ".part")):
        try:
            freed += candidate.stat().st_size
            candidate.unlink()
        except OSError:
            pass
    return freed


def model_disk_usage(model_path: str | Path) -> int:
    """Belegter Speicher der Modell-Datei in Bytes (0 wenn nicht vorhanden)."""
    model_path = Path(model_path)
    try:
        return model_path.stat().st_size
    except OSError:
        return 0


def is_model_present(model_path: str | Path) -> bool:
    return Path(model_path).is_file()
