# Gideon's Übersetzer

Windows-Desktop-Anwendung (mit CLI), die englischsprachige Bücher und Dokumente (**PDF, EPUB, DOCX**) lokal ins Deutsche übersetzt und daraus ein sauberes **EPUB 3** für den **Tolino-E-Book-Reader** erzeugt.

> **Privatsphäre zuerst:** Standardmäßig läuft alles **100 % offline** auf Ihrem eigenen Gerät – kein Internet nach dem einmaligen Modell-Download, kein API-Schlüssel, kein Buchinhalt verlässt Ihren Rechner.

---

## Highlights

- **Intuitive 3-Schritte-Bedienung:**
  1. **Dokumente auswählen (Warteschlange):** Ein oder mehrere Bücher (`PDF`, `EPUB`, `DOCX`) per Drag & Drop oder Dateidialog hinzufügen; automatische Warteschlangen-Übersicht inkl. Erkennung fortsetzbarer Zwischenspeicher.
  2. **Ausgabe & Übersetzungsmodus:** Zielordner inkl. Direktknopf *„Ordner öffnen“*, optionales Glossar und Status-Anzeige des aktiven Modells.
  3. **Übersetzung & Live-Einblick:** Fortschrittsbalken mit Restdauer-Schätzung, sofort wirksamer Abbrechen-Knopf sowie getrennte Reiter für **Live-Textprobe** und **Protokoll & Details**.
- **Kuscheliges saisonales Design & passender Installer:** Automatische Farbpaletten je nach Jahreszeit (Herbst 🍂, Winter ❄️, Frühling 🌸, Sommer ☀️) sowie feste Modi *Hell* und *Dunkel (kuschelig)* – abgestimmt mit dem Windows-Installer und App-Icon.
- **Intelligente Übersetzungs-Pipeline (ab v1.3.0):**
  - **Automatische PDF-Bereinigung:** Erkennt und entfernt wiederkehrende Kopf-/Fußzeilen (Kolumnentitel) und heilt Silbentrennungen am Zeilenende (`transla-\ntion` → `translation`).
  - **Deutsche Kapitelüberschriften & Inhaltsverzeichnis:** Erkannte englische Kapitelüberschriften werden gebündelt mit übersetzt und sauber im EPUB-Inhaltsverzeichnis (nav + NCX) abgelegt.
  - **Satzgrenzen-Chunking & Halluzinationsschutz:** Überlange Einzelabsätze werden intelligent an Satzgrenzen geteilt; fehlerhafte, zu kurze, zu lange oder unübersetzte Antworten lösen automatisch deterministische Wiederholungen (Temperatur `0.0`) aus.
  - **Intelligente Glossar-Filterung:** Bei großen Glossaren werden pro Abschnitt nur die tatsächlich vorkommenden Begriffe in den Prompt aufgenommen.
  - **Hardware-Empfehlung & Spracherkennung:** Analysiert lokal RAM und GPU für eine passende Modell-Empfehlung und warnt, falls ein Dokument bereits überwiegend auf Deutsch vorliegt.
- **Gescannte PDFs (OCR):** Seiten ohne Textebene werden automatisch per lokalem OCR (**RapidOCR**) erkannt – ohne Datenversand.
- **Unterbrechen & Fortsetzen:** Jeder übersetzte Abschnitt wird sofort zwischengespeichert; nach einem Abbruch kann genau dort fortgesetzt werden.

---

## Schnellstart (Windows)

1. Neuesten Installer `Tolino-Uebersetzer-Setup-<Version>.exe` unter [GitHub Releases](https://github.com/gschmalzhaf-cell/Gideon-s-bersetzer/releases) herunterladen und ausführen.
2. Beim ersten Start führt der **Erststart-Assistent** in zwei Klicks durch den einmaligen Download des lokalen Sprachmodells (gespeichert unter `%LOCALAPPDATA%\Tolino-Uebersetzer\models`).
3. Englischsprachige Dokumente in das Hauptfenster ziehen und **„Übersetzen starten“** klicken.

---

## Übersetzungsmodi & Modelle

| Modus | Modell / Backend | Besonderheit | Privatsphäre |
| :--- | :--- | :--- | :--- |
| **Offline (Standard)** | **Qwen2.5-7B-Instruct** (GGUF Q4_K_M, ca. 4,7 GB) | Ausgewogen für die meisten Rechner (8–16 GB RAM) | 100 % lokal |
| **Offline (Qualität)** | **TranslateGemma-12B-IT** (GGUF Q4_K_M, ca. 6,8 GB) | Spezialisiert auf Übersetzung; empfohlen ab 16 GB RAM + GPU | 100 % lokal |
| **Offline (Kompakt)** | **TranslateGemma-4B-IT** (GGUF Q4_K_M, ca. 2,3 GB) | Ideal für Rechner mit < 8 GB RAM | 100 % lokal |
| **Online-Notnagel** *(optional)* | **Mistral-API** (`mistral-small-latest`) + optional **Mistral OCR** | Nur nach bewusstem Einschalten + eigenem API-Schlüssel | Buchtext (bzw. Scan-Seiten) wird an `api.mistral.ai` gesendet |

Der Online-Betrieb wird **niemals** automatisch aktiviert. Auch die Update-Prüfung (**„Update …“**) kontaktiert GitHub ausschließlich auf ausdrücklichen Klick.

---

## Kommandozeile (CLI)

Alle Kernfunktionen stehen auch auf der Kommandozeile bereit:

```bash
# Offline-Modell verwalten
python -m gideons_uebersetzer modell laden
python -m gideons_uebersetzer modell info
python -m gideons_uebersetzer modell loeschen

# Ein oder mehrere Dokumente übersetzen (Warteschlange)
python -m gideons_uebersetzer uebersetzen buch.pdf
python -m gideons_uebersetzer uebersetzen a.pdf b.epub c.docx --out ./fertig

# Online-Notnagel (nur mit bewusstem --online)
python -m gideons_uebersetzer uebersetzen buch.pdf --tool api --online --api-key ...

# Diagnose-Report (ohne API-Schlüssel / Buchinhalte) & manuelles Update
python -m gideons_uebersetzer report
python -m gideons_uebersetzer update --check
python -m gideons_uebersetzer update

# GUI starten
python -m gideons_uebersetzer.app
```

---

## Entwicklung & Paketierung

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt   # Windows
.venv/Scripts/python -m pytest                  # Tests
```

### Windows-Installer bauen

Lokal in einem Schritt über `packaging\build-windows.bat` oder manuell:
1. CPU-Wheel von `llama-cpp-python` aus `requirements.txt` verwenden (CUDA-Builds laden auf Rechnern ohne NVIDIA-Treiber nicht).
2. `pyinstaller packaging/gideons_uebersetzer.spec --distpath packaging/dist` → Onedir-Ordner `packaging\dist\Gideons-Uebersetzer\`
3. `python packaging/check_bundle.py packaging/dist/Gideons-Uebersetzer` prüft `llama.dll`, `python312.dll` und VC-Runtime-DLLs.
4. Inno Setup 6 mit `packaging/installer.iss` kompilieren → `packaging\dist\Tolino-Uebersetzer-Setup-<Version>.exe`.

**Automatischer Release (CI):** [`.github/workflows/build-windows.yml`](.github/workflows/build-windows.yml) baut bei jedem Push auf `main` auf `windows-latest` den Installer. Sobald [`CHANGELOG.md`](CHANGELOG.md) oben einen neuen Abschnitt `## vX.Y.Z – JJJJ-MM-TT` enthält, der noch nicht als Release existiert, taggt und veröffentlicht der `auto-release`-Job die Version automatisch samt Release Notes.

Die Abnahme-Checkliste für einen frischen Windows-11-Rechner liegt in [`docs/TEST-WINDOWS.md`](docs/TEST-WINDOWS.md).

---

## Projektstruktur

```text
src/gideons_uebersetzer/
  app.py              # Einstiegspunkt GUI
  main_window.py      # Hauptfenster (3-Schritte-Bedienung), Einstellungen (3 Reiter), Zusammenfassung
  wizard.py           # Erststart-Assistent (Offline zuerst)
  theme.py            # Kuscheliges saisonales Design (QSS + dynamisches App-Icon)
  intelligence.py     # Spracherkennung, Hardware-Empfehlung, Glossar-Filter, Kapitel-Batch, Warteschlange
  pipeline.py         # Ablaufsteuerung (Kontext, Retries, Kapitelüberschriften, Cache)
  document_reader.py  # Einheitlicher Import für PDF, EPUB und DOCX
  pdf_reader.py       # PyMuPDF: Text, Kapitel-Heuristik, Kopf-/Fußzeilen- & Silbentrennungs-Bereinigung
  ocr_reader.py       # Lokales OCR (RapidOCR/ONNX) für gescannte PDFs
  mistral_ocr.py      # Optionales Mistral OCR im Online-Betrieb
  translator_base.py  # Satzgrenzen-Chunking, Prompts, Bereinigung, Qualitätsprüfung
  translator_local.py # Lokales llama.cpp (GGUF, CUDA/CPU)
  translator_api.py   # Mistral-API (Streaming, Zeichenzählung)
  epub_builder.py     # EPUB 3 für den Tolino (nav + NCX, Typografie »…«, Deckbild)
  cache.py            # JSON-Zwischenspeicher zum Fortsetzen
  model_manager.py    # Modell-Download mit Fortschritt/Fortsetzen/Löschen
  settings.py         # Persistierte Einstellungen (settings.json)
  report.py           # Datenschutzfreundlicher Diagnose-Report (Markdown + JSON)
  updater.py          # Manuelle GitHub-Release-Prüfung & Installer-Download
  cli.py              # Kommandozeilen-Interface
packaging/            # PyInstaller-Spec, Inno-Setup-Skript, Asset-Generator, Bundle-Check
tests/                # pytest-Testsuite (inkl. GUI-Smoke-Tests)
```

---

## Ideen & Vorschläge für weitere Features und Optimierungen

Hier sind konkrete nächste Ausbaustufen, die die App noch hilfreicher, schneller und komfortabler machen (siehe auch [`docs/ROADMAP.md`](docs/ROADMAP.md)):

### 1. Übersetzungsqualität & Intelligenz
- **Automatisches Buch-Glossar vorab erzeugen:** Vor der eigentlichen Übersetzung scannt die App das Buch nach wiederkehrenden Eigennamen, Orten und Fachbegriffen, schlägt eine konsistente Übersetzungstabelle vor (bearbeitbar vom Nutzer) und nutzt sie automatisch für das gesamte Buch.
- **Stil- & Genre-Profile:** Auswählbare Profile in den Einstellungen – z. B. *Roman / Belletristik* (flüssig, literarisch), *Sachbuch* (klar, präzise), *Fachbuch / Technik* (englische Fachbegriffe in Klammern oder unverändert lassen).
- **Zweisprachiges EPUB ([#2](https://github.com/gschmalzhaf-cell/Gideon-s-bersetzer/issues/2)):** Option *„Zweisprachig ausgeben“*, die Originalabsatz (Englisch) und Übersetzung (Deutsch) direkt untereinander oder abwechselnd darstellt – ideal zum Sprachenlernen oder Gegenlesen.
- **Gezieltes Nachübersetzen fehlgeschlagener Abschnitte:** Statt ein ganzes Buch neu zu starten, lassen sich im Abschluss-Dialog oder über den Zwischenspeicher gezielt nur fehlgeschlagene Abschnitte erneut übersetzen (z. B. mit einem anderen Modell oder geänderter Abschnittsgröße).
- **Erweiterte Sprachpaare:** Neben Englisch → Deutsch auch weitere Ausgangssprachen (z. B. Französisch, Spanisch, Italienisch) mit automatischer Ausgangssprachen-Erkennung.

### 2. Bedienung & E-Reader-Workflow
- **Direkt-Export auf den Tolino:** Automatische Erkennung eines per USB angeschlossenen Tolino-Readers (Laufwerk mit `Books/`-Ordner) und Ein-Klick-Knopf *„Auf Tolino kopieren“* im Abschluss-Dialog.
- **Warteschlange per Drag & Drop sortieren & pausieren:** Reihenfolge der Bücher in der Liste direkt per Ziehen ändern sowie eine echte *„Pause / Weiter“*-Funktion zwischen zwei Abschnitten.
- **Vorab-Zeitschätzung pro Dokument:** Nach dem Hinzufügen zeigt die Warteschlange nicht nur die Dateigröße, sondern auf Basis der Hardware (CPU/GPU) und Wortzahl eine grobe geschätzte Dauer pro Buch an.
- **Integrierte EPUB-Kurzansicht:** Nach Abschluss das erste Kapitel und das Inhaltsverzeichnis direkt in einem Vorschau-Dialog prüfen, bevor die Datei auf den Reader wandert.

### 3. Leistung & Technik
- **Vulkan- / DirectML-GPU-Beschleunigung zusätzlich zu CUDA:** Damit auch AMD- und Intel-Grafikkarten unter Windows von deutlicher Beschleunigung profitieren (aktuell greift GPU-Offload nur bei NVIDIA/CUDA).
- **Automatisches Speichern des letzten Arbeitsstands beim Beenden:** Wenn das Fenster während einer Übersetzung geschlossen wird, sauber nachfragen und den Zwischenspeicher ohne Datenverlust sichern.
- **Parallele Anfragen im Online-Notnagel:** Bei Nutzung der Mistral-API optional 2–3 Abschnitte parallel übersetzen (unter Beibehaltung der Reihenfolge und Rate-Limit-Backoff), um Bücher in wenigen Minuten fertigzustellen.
- **Fußnoten- & Tabellen-Erhaltung:** Fußnoten in PDFs/EPUBs sauber als klickbare EPUB-Endnoten statt mitten im Fließtext ablegen.
