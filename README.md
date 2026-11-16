# Gideon's Übersetzer

Windows-Anwendung, die englischsprachige PDF-Dokumente ins Deutsche übersetzt
und daraus eine EPUB-Datei für den Tolino-E-Book-Reader erzeugt.

- **Offline (Standard):** eingebettetes llama.cpp (llama-cpp-python) mit
  Mistral-7B-Instruct-v0.3 als GGUF (Q4_K_M, ca. 4,4 GB). Das Modell wird beim
  ersten Start einmalig heruntergeladen und liegt unter
  `%LOCALAPPDATA%\Tolino-Uebersetzer\models`. Danach läuft die Übersetzung
  vollständig lokal – kein Internet, kein API-Schlüssel.
- **Notnagel (optional, nur nach bewusstem Einschalten):** Mistral-API
  (`https://api.mistral.ai/v1/chat/completions`, Modell `mistral-small-latest`,
  Streaming). In diesem Modus wird der Buchtext an Mistral übertragen; das steht
  im Assistenten und in den Einstellungen.

## Meilensteine

- **M1** – Kern ohne GUI: CLI liest ein PDF (PyMuPDF, Kapitelerkennung über
  Schriftgrößen-Heuristik), übersetzt lokal Abschnitt für Abschnitt
  (llama.cpp) und schreibt ein gültiges EPUB 3 (nav + NCX, deutsche
  Anführungszeichen, Titelseite, optionales Deckbild). Inkl. Modellverwaltung
  (Download mit Fortschritt/Abbruch/Fortsetzen, Löschen) und JSON-Zwischenspeicher
  zum Fortsetzen abgebrochener Übersetzungen.
- **M2** – Mistral-API als Notnagel in der CLI (Streaming, Fehlerbehandlung,
  Zeichenzählung) – nur mit eingetragenem Schlüssel und bewusstem Einschalten.
- **M3** – PySide6-GUI: Hauptfenster mit Import (Dialog + Drag & Drop),
  Fortschrittsbalken, Live-Textprobe, Abbrechen, Erststart-Assistent,
  Einstellungen, Fortsetzen nach Unterbrechung.
- **M4** – Härtung (Qualitätsprüfung, Wiederholungen, Abschluss-Zusammenfassung),
  PyInstaller-Build (eine .exe) und Inno-Setup-Installer
  (`Tolino-Uebersetzer-Setup.exe`, ohne Modell, mit deutscher README).

## Entwicklung

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt   # Windows
.venv/Scripts/python -m pytest                  # Tests
```

CLI (M1/M2):

```bash
python -m gideons_uebersetzer modell laden                          # Offline-Modell laden
python -m gideons_uebersetzer modell info                           # Modell/Speicher anzeigen
python -m gideons_uebersetzer modell loeschen                       # Modell löschen
python -m gideons_uebersetzer uebersetzen buch.pdf                  # offline übersetzen
python -m gideons_uebersetzer uebersetzen buch.pdf --tool api --online --api-key ...
```

GUI (M3):

```bash
python -m gideons_uebersetzer.app
```

## Paketierung (Windows, M4)

1. CUDA-Build von `llama-cpp-python` installieren (siehe requirements.txt).
2. `pyinstaller packaging/gideons_uebersetzer.spec --distpath packaging/dist` → `packaging\dist\Gideons-Uebersetzer.exe`
3. Inno Setup 6 mit `packaging/installer.iss` kompilieren → `packaging\dist\Tolino-Uebersetzer-Setup.exe`

oder lokal alles auf einmal: `packaging\build-windows.bat`

**Automatisch (CI):** `.github/workflows/build-windows.yml` baut bei jedem Push auf `main`
(und bei Tags `v*`) auf einem `windows-latest`-Runner den Installer. Push auf `main` → Artefakt
im Job + aktualisierter Draft-Release `latest-build`; Tag `v*.*` → veröffentlichter Release.

**Release nach jeder Änderung (automatisch):** Sobald `CHANGELOG.md` oben einen neuen Abschnitt
`## vX.Y.Z – …` enthält, der noch nicht als Tag existiert, pusht der `auto-release`-Job nach dem
green Build automatisch den Tag `vX.Y.Z` → der Workflow veröffentlicht den Release inklusive der
Release Notes aus genau diesem Abschnitt. Vorgehen also: Änderung committen, CHANGELOG-Abschnitt
ergänzen, auf `main` pushen – Release erscheint von allein.

Der Installer enthält **nicht** das Modell; die Anwendung lädt es beim ersten
Start selbst. Siehe `packaging/README-de.txt`. Die Abnahme-Checkliste für einen
frischen Windows-11-Rechner (1-Klick-Beweis, Offline-Beweis, epubcheck, Calibre,
Tolino, Privatsphäre, Fortsetzen) liegt in [docs/TEST-WINDOWS.md](docs/TEST-WINDOWS.md).

## Roadmap (nach v1.0)

 siehe [docs/ROADMAP.md](docs/ROADMAP.md) bzw. die Issues [#1](https://github.com/gschmalzhaf-cell/Gideon-s-bersetzer/issues/1) (EPUB/DOCX als Eingabe), [#2](https://github.com/gschmalzhaf-cell/Gideon-s-bersetzer/issues/2) (zweisprachiges EPUB), [#3](https://github.com/gschmalzhaf-cell/Gideon-s-bersetzer/issues/3) (OCR für gescannte PDFs).

## Privatsphäre

Ohne eingeschalteten Online-Betrieb verlässt kein Buchinhalt das Gerät: die
Übersetzung läuft vollständig lokal. Der Online-Betrieb (Mistral-API) wird
niemals automatisch aktiviert.

## Struktur

```
src/gideons_uebersetzer/
  settings.py         # settings.json im Benutzerprofil
  pdf_reader.py       # PyMuPDF: Text, Kapitel-Heuristik, Scan-Erkennung
  translator_base.py  # Chunking, Prompts, Glossar, Qualitätsprüfung
  translator_local.py # llama.cpp (GGUF, CUDA/CPU)
  translator_api.py   # Mistral-API (Streaming)
  epub_builder.py     # EPUB 3 für den Tolino
  cache.py            # JSON-Zwischenspeicher (Fortsetzen)
  model_manager.py    # Modell-Download/Prüfen/Löschen
  pipeline.py         # Ablaufsteuerung (CLI + GUI)
  cli.py              # Kommandozeile (M1/M2)
  main_window.py      # Hauptfenster (M3)
  wizard.py           # Erststart-Assistent (M3)
  app.py              # Einstiegspunkt GUI (M3)
packaging/            # PyInstaller-Spec, Inno-Setup-Skript, README-de.txt
tests/                # pytest
```
