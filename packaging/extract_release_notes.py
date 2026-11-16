#!/usr/bin/env python
"""Extrahiert die Release Notes für ein Tag aus CHANGELOG.md.

Aufruf: python packaging/extract-release-notes.py <tag> <changelog> <ausgabe>
Beispiel: python packaging/extract-release-notes.py v1.1.0 CHANGELOG.md release-notes.txt

Der Abschnitt zwischen der Überschrift "## <tag>" und der nächsten "## "-Überschrift
wird geschrieben. Fallback (Tag ohne Abschnitt): kurzer Standardtext.
"""

from __future__ import annotations

import sys
from pathlib import Path

FALLBACK = (
    "Installer: Tolino-Uebersetzer-Setup-<Version>.exe (Dateiname enthält die Release-Version). "
    "Enthält NICHT das Übersetzungsmodell – "
    "die App lädt es beim ersten Start selbst (Assistent, Offline-Weg an erster Stelle). "
    "Details: README.md und packaging/README-de.txt im Repository.\n"
)


def extract_notes(tag: str, changelog: Path) -> str:
    lines = changelog.read_text(encoding="utf-8").splitlines()
    start = None
    for i, line in enumerate(lines):
        heading = line.strip().lstrip("#").strip()
        if heading.startswith(tag) or heading.startswith(f"[{tag}]"):
            start = i
            break
    if start is None:
        return FALLBACK
    body: list[str] = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        body.append(line)
    text = "\n".join(body).strip()
    return text or FALLBACK


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(__doc__)
        return 2
    tag, changelog, out = argv[1], Path(argv[2]), Path(argv[3])
    notes = extract_notes(tag, changelog)
    out.write_text(notes + "\n", encoding="utf-8")
    print(f"Release Notes für {tag} ({len(notes)} Zeichen) -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
