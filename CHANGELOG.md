# Änderungsprotokoll – Gideon's Übersetzer

Die Release Notes jedes veröffentlichten Releases (Tag `v*`) werden aus dem
passenden Abschnitt dieser Datei erzeugt (siehe `.github/workflows/build-windows.yml`
und `packaging/extract_release_notes.py`).

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
