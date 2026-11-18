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

## v1.2.5 – 2026-11-18

### Behoben
- **Abschnitts-Überschriften („1. …“, „2. …“, „3. …“ sowie Karten-Titel in den Einstellungen)
  saßen auf der Rahmenlinie und wirkten verrutscht:** `QGroupBox::title` saß bisher mit
  `subcontrol-origin: margin` auf der oberen Rahmenkante, wodurch Qt hinter dem Titel einen
  andersfarbigen Ausschnitt im Hintergrund-Farbverlauf gerendert hat. Die Überschriften liegen
  jetzt mit `subcontrol-origin: padding` sauber als bündige Karten-Kopfzeile innerhalb der
  abgerundeten Boxen.

## v1.2.4 – 2026-11-18

### Neu
- **Intuitive 3-Schritte-Bedienung im Hauptfenster:** Das Hauptfenster ist jetzt klar in drei
  nummerierte Bereiche gegliedert:
  1. *Dokumente auswählen (Warteschlange)* – mit sichtbarem Drag-&-Drop-Hinweis und klaren
     Listen-Aktionen („+ Dokumente hinzufügen …“, „Auswahl entfernen“, „Liste leeren“),
  2. *Ausgabe & Übersetzungsmodus* – Zielordner inkl. Direktknopf „Ordner öffnen“, optionales
     Glossar sowie Status-Badge des aktiven Werkzeugs (zeigt im Offline-Modus direkt an, ob und
     welches lokale Modell bereitsteht),
  3. *Übersetzung & Live-Einblick* – Hauptaktion „Übersetzen starten“ direkt neben dem
     Fortschrittsbalken; darunter zwei übersichtliche Reiter für „Live-Textprobe (aktueller
     Abschnitt)“ und „Protokoll & Details“ statt zweier übereinander gequetschter Textfelder.
- **Einstellungen in 3 übersichtlichen Reitern:** „Allgemein & Modus“ (Design, Zielordner,
  Glossar, Offline/Online-Werkzeug mit automatischer Aktivierung der API-Felder),
  „Offline-Modell“ (Modell-Auswahl, Speicherstatus, Laden/Löschen, Erststart-Assistent) und
  „Qualität & OCR“ (Temperatur, Abschnittsgröße, lokale oder Mistral-OCR).
- **Installer im kuscheligen App-Design & eigenes App-Icon:** Neues Buch-Wappen-Icon
  (`packaging/app_icon.ico`) für EXE, Fenster, Desktop-/Startmenü-Verknüpfungen und
  Setup-Datei sowie passende Inno-Setup-Banner (`wizard_banner.bmp`, `wizard_small.bmp`)
  und warme Creme-/Kastanien-Farbgebung im Installations-Assistenten (`InitializeWizard`).

### Geändert
- **Design abgerundet (`theme.py`):** Klare visuelle Hierarchie zwischen primären
  Hauptaktionen (kräftiger Akzent-Button für „Übersetzen starten“, „Gewähltes Modell laden“,
  „Speichern“) und sekundären Buttons (ruhiger, warm gerahmter Kartenton); dazu passend
  gestaltete Reiter (`QTabWidget`), Checkbox-/Radio-Indikatoren, Status-Badges und ein
  abgerundeter Erststart-Assistent.

## v1.2.3 – 2026-11-18

### Neu
- **Kuscheliges saisonales Design:** neues Theme-Modul (`theme.py`) mit Qt-Stylesheet.
  Standard-Modus „Automatisch (saisonal)“ wechselt die Palette mit der Jahreszeit – aktuell
  **Herbst** (warmes Creme/Amber, Akzent Kastanie, 🍂 im Fenstertitel und als Gruß-Label),
  dazu Winter (❄️, eisiges Blau mit Kerzenrot), Frühling (🌸) und Sommer (☀️). Dazu
  abgerundete Buttons und Eingabefelder, warmer Farbverlauf im Fensterhintergrund,
  Akzentfarbe für Fortschrittsbalken und Textauswahl. Fest wählbar in den Einstellungen
  (Design-Dropdown): „Hell“ und „Dunkel (kuschelig)“; wird live übernommen und erscheint im
  Diagnose-Report.

### Behoben
- **CI: GUI-Smoke-Tests crashten nach „alle Tests bestanden“ mit Zugriffsverletzung
  (0xC0000005) beim Prozess-Teardown** – der Build schlug dadurch mit Exitcode 1 fehl.
  Qt wird in den Tests jetzt kontrolliert abgebaut (Fenster schließen, `deleteLater`,
  QApplication per `shiboken6.delete` freigeben), und das App-Stylesheet wird nicht mehr in
  jedem `MainWindow.__init__` erneut gesetzt (einmalig in `app.py` bzw. nach Einstellungs-OK).

## v1.2.2 – 2026-11-17

### Geändert
- **Packaging: Onedir statt Onefile.** Die App wird jetzt als Ordner installiert
  (`Gideons-Uebersetzer.exe` + `_internal\`), nicht mehr als einzelne EXE, die sich bei jedem
  Start nach `%TEMP%\_MEI...` entpackt. Hintergrund: der wiederkehrende Startfehler
  „Failed to load Python DLL ... python312.dll – LoadLibrary: Das angegebene Modul wurde nicht
  gefunden“ tritt bei Onefile-Builds auf, wenn ein Antivirus (z. B. Windows Defender) eine frisch
  entpackte DLL im temporären `_MEI`-Verzeichnis quarantäniert. Ohne Temp-Extrakt entfällt diese
  Fehlerquelle; die VC-Runtime-DLLs liegen außerdem weiterhin garantiert im Bundle.
- **CI-Bundle-Check jetzt für Onedir:** `packaging/check_bundle.py` akzeptiert außer der EXE auch
  den App-Ordner (`packaging/dist/Gideons-Uebersetzer`) und prüft `llama.dll`/`ggml`,
  `python312.dll`, `vcruntime140.dll` sowie sämtliche Importe von `python312.dll`
  (im Bundle oder Windows-System-DLL). Läuft in CI und in `build-windows.bat`.

## v1.2.1 – 2026-11-17

### Behoben
- **Übersetzen im Mistral-API-Modus schlug mit HTTP 422 fehl:** Bei gewähltem
  TranslateGemma-Preset wurde das strukturierte Prompt-Format (user-content als Liste mit
  `source_lang_code`/`target_lang_code`) auch an die Mistral-API geschickt, die nur
  String-Content akzeptiert – jeder Abschnitt endete mit „Input should be a valid
  string“. Das TranslateGemma-Format wird jetzt nur noch im Offline-Betrieb (lokal via
  llama.cpp, Chat-Template des GGUF) verwendet; im API-Betrieb immer das Standard-Format.
- **Start der EXE auf Rechnern ohne installiertes VC++-Redist abgesichert:** `python312.dll`
  hängt an `vcruntime140.dll` (Startfehler „Failed to load Python DLL … LoadLibrary: Das
  angegebene Modul wurde nicht gefunden“). Die VC-Runtime-DLLs werden jetzt explizit in
  die EXE gebündelt, und ein neuer CI-Schritt (`packaging/check_bundle.py`, läuft auch im
  lokalen `build-windows.bat`) prüft, dass `python312.dll` + `vcruntime140.dll` im Bundle
  liegen und dass jede von `python312.dll` importierte DLL im Bundle oder eine
  Windows-System-DLL ist – sonst schlägt der Build fehl (der Smoke-Test allein merkt das
  nicht, weil der CI-Runner das Redist installiert hat).

## v1.2.0 – 2026-11-16

### Neu
- **Warteschlange (mehrere Dokumente nacheinander):** GUI: Liste mit „Hinzufügen …“ /
  „Entfernen“ / „Leeren“, Drag & Drop nimmt mehrere Dateien; Start arbeitet die Liste
  sequenziell ab (einmalig geladenes Modell wird für alle Dokumente wiederverwendet,
  Fehler bei einem Dokument brechen die Schlange nicht ab, am Ende Sammel-Übersicht).
  CLI: `uebersetzen buch1.pdf buch2.epub buch3.docx …` (positional nargs="+"), pro Dokument
  eigene Zusammenfassung, Exitcode 1 wenn eines fehlschlägt.
- **EPUB und DOCX als Eingabeformate** (schließt #1): neuer `document_reader.py` liest
  EPUB (ebooklib, Spine-Reihenfolge, h1–h4 als Kapitel) und DOCX (python-docx, Heading-Stile
  als Kapitel) in dieselbe Kapitel/Absatz-Struktur wie PDFs. Dateidialog und Drag & Drop
  akzeptieren `*.pdf *.epub *.docx`.

## v1.1.7 – 2026-11-16

### Neu
- **Modell-Auswahl (Presets) in den Einstellungen:** Qwen2.5-7B-Instruct (empfohlen, 4,7 GB),
  **TranslateGemma-12B-IT** (spezialisiert auf Übersetzung, 6,8 GB) und TranslateGemma-4B-IT
  (kompakt, 2,3 GB). „Modell laden“ lädt das gewählte Preset. TranslateGemma bekommt ein
  eigenes Prompt-Format (kein System-Prompt, strukturiertes user-content en→de laut seinem
  Chat-Template). Wird ein älteres Legacy-Modell erkannt, erscheint ein Hinweis in den
  Einstellungen; der Report zeigt Preset + Legacy-Flag.

### Behoben
- **Modell-Download in den Einstellungen:** echter Fortschrittsbalken mit MB/s und
  funktionierendem Abbrechen (QProgressDialog + Worker-Thread); wenn das gewählte Modell schon
  lokal liegt, kommt sofort ein Hinweis statt eines leeren Dialogs.
- **Live-Textprobe:** robusteres Anhängen der Token (Cursor ans Ende, insertPlainText) plus
  GUI-Regressionstest.

## v1.1.6 – 2026-11-16

### Neu
- **Update-Funktion (manuell, nie automatisch):** Knopf „Update …“ in der GUI bzw. CLI `update`
  prüft die neueste GitHub-Release (`api.github.com`), lädt bei Bedarf den versionierten Installer
  (`Tolino-Uebersetzer-Setup-<Version>.exe`) mit Fortschritt/Abbruch/Fortsetzen von github.com und
  startet ihn (gleiche AppId → Upgrade der bestehenden Installation; die App beendet sich dafür).
  `update --check` prüft nur. Es gibt keinen Auto-Check beim Start – der Offline-Standard bleibt
  unangetastet; die Update-Prüfung kontaktiert GitHub nur auf ausdrücklichen Klick und meldet das.

## v1.1.5 – 2026-11-16

### Neu
- **Diagnose-Report:** neuer CLI-Befehl `report` und ein Knopf „Report erstellen …“ in der GUI.
  Erzeugt eine einzelne Markdown-Datei (Klartext-Abschnitte + JSON-Anhang) mit App-Version,
  Plattform, Einstellungen (API-Schlüssel redigiert), Modell-Status, OCR-Backend, allen
  Zwischenspeichern inklusive fehlgeschlagener Abschnitte samt Qualitäts-Problem und kurzem
  Quelltext-Ausschnitt (max. 300 Zeichen) sowie dem Log-Tail. Zum Fehlerfinden bzw. zur
  Qualitätsverbesserung einfach die Datei weitergeben – sie enthält weder API-Schlüssel
  noch Buchinhalte.

## v1.1.4 – 2026-11-16

### Neu
- **Besseres lokales Standardmodell:** Qwen2.5-7B-Instruct (Q4_K_M, ca. 4,7 GB, 32k Kontext)
  statt Mistral-7B-Instruct-v0.3 – deutlich robustere deutsche Übersetzungen, weniger
  Prompt-Echos. Bereits heruntergeladene Mistral-Modelle werden weiterhin verwendet
  (kein erneuter Download); das Modell ist wie gehabt in den Einstellungen änderbar.
- **Mistral OCR als optionales OCR-Backend** (Einstellungen/CLI `--ocr-backend mistral`):
  gescannte Seiten werden dann über die Mistral-OCR-API (`mistral-ocr-latest`) erkannt.
  Nur im bewusst eingeschalteten Online-Betrieb aktiv – dann werden die Seitenbilder
  der Scans an Mistral übertragen (Text-Seiten nicht). Standard bleibt lokales RapidOCR.

### Geändert
- **Modell-Antworten werden bereinigt, bevor sie geprüft werden:** Code-Fences,
  führende „Translation:“-/„Übersetzung:“-Zeilen, Anführungszeichen um den gesamten
  Text und Chat-Template-Reste werden abgeschnitten. Retries laufen mit Temperatur 0
  und einem verschärften Hinweis („jeden Satz vollständig übersetzen“).

## v1.1.3 – 2026-11-16

### Behoben
- **llama.dll lädt im fertigen Installer nicht** („Failed to load shared library …
  not found when the application was frozen“): Das bis dato gebündelte CUDA-Build von
  llama-cpp-python (cu124) hängt zur Laufzeit am NVIDIA-Treiber (nvcuda.dll) und ist auf
  Rechnern ohne GPU nicht ladbar. Der Release-Build bündelt jetzt das CPU-Wheel von PyPI.
  Zusätzlich sammelt PyInstaller die nativen DLLs (`llama_cpp/lib/*.dll`) jetzt pro
  Collector einzeln, damit ein Importfehler auf dem Build-Rechner die DLLs nicht mehr aus
  dem Bundle wirft. Neuer CI-Check: llama_cpp muss auf dem Runner ladbar sein und
  llama.dll + ggml-DLLs müssen im EXE-Bundle liegen.

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
