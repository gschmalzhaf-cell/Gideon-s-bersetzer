# Änderungsprotokoll – Gideon's Übersetzer

Die Release Notes jedes veröffentlichten Releases (Tag `v*`) werden aus dem
passenden Abschnitt dieser Datei erzeugt (siehe `.github/workflows/build-windows.yml`
und `packaging/extract_release_notes.py`).

<!--
TEMPLATE für einen neuen Abschnitt (einfach einkommentieren und ausfüllen):

## vX.Y.Z – JJJJ-MM-TT

### Neu
- …

### Geändert
- …

### Behoben
- …

### Entfernt
- …

Konventionen: neueste Version oben; Datum ISO (JJJJ-MM-TT); Sprache Deutsch;
ur Abschnitte aufführen, die es wirklich gibt; Features kurz und aus
Anwendersicht beschreiben (was ändert sich beim Installieren/Nutzen?).
-->

## v1.1.2 – 2026-11-16

### Geändert
- **Installer-Datei trägt die Versionsnummer:** `Tolino-Uebersetzer-Setup-<Version>.exe`
  (z. B. `Tolino-Uebersetzer-Setup-1.1.2.exe`). Die Version kommt aus dem Tag `v*`
  bzw. bei main-Builds aus dem obersten `## vX.Y.Z`-Abschnitt in CHANGELOG.md;
  der lokale Build (`packaging/build-windows.bat`) liest dieselbe Version aus dem CHANGELOG.

### Behoben
- **Modell-Download schlug mit 404 fehl:** Hugging Face hat die GGUF-Dateien umbenannt
  (neues Namensschema mit Bindestrich statt Punkt vor der Quantisierung). Standard-Datei
  ist jetzt `Mistral-7B-Instruct-v0.3-Q4_K_M.gguf`. Eine bereits unter dem alten Namen
  (`Mistral-7B-Instruct-v0.3.Q4_K_M.gguf`) vorhandene Datei wird weiterhin verwendet –
  kein erneuter 4,4-GB-Download.

## v1.1.1 – 2026-11-15

### Behoben
- **Startfehler des Installers:** „Failed to execute script 'app' … attempted relative
  import with no known parent package“. Ursache: PyInstaller-Entry-Skript mit relativen
  Importen. Jetzt dünner Einstiegspunkt `packaging/entry.py` mit absolutem Import;
  zusätzlich CI-Smoke-Test („EXE --version“ muss mit Exitcode 0 enden), damit ein solcher
  Importfehler nie wieder unbemerkt in ein Release gelangt.

## v1.1.0 – 2026-11-15

### Neu
- **OCR für gescannte PDFs:** Seiten ohne Textebene werden automatisch per OCR
  erkannt (RapidOCR/ONNX, 200 dpi, vollständig lokal – die Modelle sind in der
  EXE gebündelt). Gemischte PDFs (Text + Scan) funktionieren ebenfalls.
  Kapitel-Erkennung im OCR-Text per Heuristik; Fortschritt pro Seite im Protokoll.
- Einstellung „OCR für gescannte PDFs“ in den Einstellungen (Standard: an);
  CLI-Flag `--no-ocr`. Bei ausgeschaltetem OCR klare Abbruchmeldung.

### Geändert
- Installer wächst auf ca. 470 MiB (ONNX-Runtime + OCR-Modelle + OpenCV gebündelt).

### Behoben
- GUI-Test auf dem Windows-Runner (QWizard: `pageIds()` statt `pageCount()`).

## v1.0.0 – 2026-11-14

### Neu
- Erste fertige Version: englische PDFs ins Deutsche übersetzen und als EPUB 3
  für den Tolino ausgeben – per Ein-Klick-Installer `Tolino-Uebersetzer-Setup.exe`
  (kein separates Python, kein Ollama).
- **Offline (Standard):** eingebettetes llama.cpp (GGUF Q4_K_M, Mistral-7B-Instruct-v0.3,
  ca. 4,4 GB), Modell-Download beim ersten Start mit Fortschritt, Geschwindigkeit,
  Abbrechen und Fortsetzen; Ablage unter `%LOCALAPPDATA%\Tolino-Uebersetzer\models`.
  CUDA-Beschleunigung falls vorhanden, sonst CPU mit klarer Warnung.
- **Notnagel (optional, nur nach bewusstem Einschalten):** Mistral-API
  (`mistral-small-latest`, Streaming) mit API-Schlüssel; Zusammenfassung mit
  gesendeten Zeichen (Kostenschätzung).
- PDF-Import per Dialog und Drag & Drop; Kapitelerkennung per Schriftgrößen-Heuristik.
- Übersetzung Abschnitt für Abschnitt (~1500 Wörter) mit Stützkontext und Glossar
  („Begriff = Übersetzung“-Datei); Qualitätsprüfung je Abschnitt (Länge, Prompt-Reste,
  unübersetzter Text) mit bis zu 2 Wiederholungen, danach Notiz im EPUB.
- Fortschrittsbalken mit Seite, Abschnitten, geschätzter Restdauer, Live-Textprobe;
  Abbrechen wirkt sofort; unterbrochene Übersetzungen per JSON-Zwischenspeicher
  mit einem Klick fortsetzbar.
- EPUB 3 ohne DRM: nav + NCX, `dc:language=de`, deutsche Anführungszeichen (»…«),
  Titelseite mit Hinweis, optionales Deckbild aus Seite 1.
- Erststart-Assistent (Offline an erster Stelle, 2 Klicks bis betriebsbereit),
  Einstellungen persistiert in `settings.json`.
- Automatischer Windows-Build je Push/Tag via GitHub Actions.
