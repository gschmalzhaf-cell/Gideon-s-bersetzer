"""Update-Funktion: prüft GitHub-Releases auf eine neuere Version, lädt den Installer, startet ihn.

Manuell auslösbar (GUI-Knopf „Update …“ / CLI `update`) – es gibt KEINEN automatischen
Check beim Start, damit der Offline-Standard (kein Datenverkehr ohne bewusste Aktion)
ungetastet bleibt. Die Prüfung kontaktiert api.github.com, der Download lädt von
github.com; beides wird im UI-Text klar benannt.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import requests

from . import __version__

GITHUB_REPO = "gschmalzhaf-cell/Gideon-s-bersetzer"
RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
INSTALLER_ASSET_RE = re.compile(r"^Tolino-Uebersetzer-Setup-(\d+\.\d+\.\d+)\.exe$", re.IGNORECASE)
CONNECT_TIMEOUT = 10
READ_TIMEOUT = 120
CHUNK_BYTES = 1024 * 1024


class UpdateError(Exception):
    """Update-Fehler mit deutscher, anzeigbarer Meldung."""


class UpdateCancelled(Exception):
    """Der Anwender hat den Update-Download abgebrochen."""


def parse_version(v: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums) if nums else (0,)


def is_newer(remote: str, local: str) -> bool:
    return parse_version(remote) > parse_version(local)


def latest_release() -> dict:
    """Liefert {'version', 'asset_name', 'asset_url'} der neuesten veröffentlichten GitHub-Release."""
    try:
        resp = requests.get(RELEASES_API, headers={"Accept": "application/vnd.github+json"}, timeout=(CONNECT_TIMEOUT, 15))
    except requests.RequestException as exc:
        raise UpdateError(f"GitHub ist nicht erreichbar: {exc}") from exc
    if resp.status_code != 200:
        raise UpdateError(f"GitHub-API antwortet mit HTTP {resp.status_code}.")
    try:
        data = resp.json()
    except ValueError as exc:
        raise UpdateError("Unerwartete Antwort der GitHub-API (kein JSON).") from exc
    version = (data.get("tag_name") or "").lstrip("v")
    if not parse_version(version) or parse_version(version) == (0,):
        raise UpdateError("Die neueste Release trägt keinen Versions-Tag (vX.Y.Z).")
    best: tuple[tuple[int, ...], str, str] | None = None
    for asset in data.get("assets", []):
        m = INSTALLER_ASSET_RE.match(asset.get("name", ""))
        url = asset.get("browser_download_url") or ""
        if m and url:
            candidate = (parse_version(m.group(1)), asset["name"], url)
            if best is None or candidate[0] > best[0]:
                best = candidate
    if best is None:
        raise UpdateError(f"Release v{version} enthält keinen Installer (Tolino-Uebersetzer-Setup-<Version>.exe).")
    return {"version": version, "asset_name": best[1], "asset_url": best[2]}


def check_for_update() -> dict | None:
    """Liefert die Release-Dict, wenn eine neuere Version als die laufende existiert, sonst None."""
    rel = latest_release()
    if is_newer(rel["version"], __version__):
        return rel
    return None


def default_download_dir() -> Path:
    return Path(tempfile.gettempdir()) / "Tolino-Uebersetzer-Update"


def download_installer(
    url: str,
    dest_dir: Path,
    asset_name: str | None = None,
    progress_cb=None,
    cancel_event: threading.Event | None = None,
) -> Path:
    """Lädt den Installer mit Fortschritt/Abbruch und .part-Fortsetzung. Liefert den Pfad."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = asset_name or url.rsplit("/", 1)[-1] or "Tolino-Uebersetzer-Setup-update.exe"
    dest = dest_dir / name
    part = dest_dir / (name + ".part")
    if dest.is_file():
        return dest

    downloaded = part.stat().st_size if part.is_file() else 0
    headers = {"User-Agent": f"Gideons-Uebersetzer/{__version__}"}
    if downloaded:
        headers["Range"] = f"bytes={downloaded}-"
    try:
        resp = requests.get(url, headers=headers, stream=True, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
    except requests.RequestException as exc:
        raise UpdateError(f"Der Update-Download konnte nicht gestartet werden: {exc}") from exc
    if resp.status_code == 416 or (resp.status_code == 200 and downloaded > 0):
        resp.close()
        try:
            part.unlink()
        except OSError:
            pass
        downloaded = 0
        resp = requests.get(url, headers={"User-Agent": f"Gideons-Uebersetzer/{__version__}"}, stream=True, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
    if resp.status_code not in (200, 206):
        resp.close()
        raise UpdateError(f"GitHub hat den Download abgelehnt (HTTP {resp.status_code}).")
    total = downloaded + int(resp.headers.get("Content-Length") or 0)
    if resp.status_code == 200:
        downloaded = 0
    start = time.monotonic()
    last = start
    last_bytes = downloaded
    speed = 0.0
    try:
        with open(part, "ab") as fh:
            for block in resp.iter_content(chunk_size=CHUNK_BYTES):
                if cancel_event is not None and cancel_event.is_set():
                    raise UpdateCancelled("Download abgebrochen.")
                if not block:
                    continue
                fh.write(block)
                downloaded += len(block)
                now = time.monotonic()
                if now - last >= 0.5:
                    instant = (downloaded - last_bytes) / (now - last)
                    speed = 0.7 * speed + 0.3 * instant if speed else instant
                    last, last_bytes = now, downloaded
                    if progress_cb is not None:
                        progress_cb(downloaded, total, speed)
    except requests.RequestException as exc:
        raise UpdateError(f"Der Update-Download wurde unterbrochen: {exc}") from exc
    finally:
        resp.close()
    os.replace(part, dest)
    if progress_cb is not None:
        progress_cb(downloaded, total, speed)
    return dest


def run_installer(installer_path: Path) -> None:
    """Startet den Inno-Setup-Installer (gleiche AppId → Upgrade der bestehenden Installation)."""
    path = str(installer_path)
    if sys.platform.startswith("win"):
        subprocess.Popen([path])
    else:
        subprocess.Popen(["xdg-open", path])
