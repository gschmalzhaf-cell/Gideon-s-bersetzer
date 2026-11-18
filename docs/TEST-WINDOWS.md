# Abnahme-Checkliste auf einem frischen Windows 11 (64 Bit)

Voraussetzung: Rechner ohne installiertes Python, ohne Ollama, Windows 10/11, 16 GB RAM,
Mittelklasse-GPU (ca. 8 GB VRAM) für den CUDA-Pfad.

## 1. Build des Installers (einmalig, auf dem Build-Rechner)

```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt pyinstaller
:: Für CUDA: vorher das CUDA-Build von llama-cpp-python installieren
:: (siehe requirements.txt) – sonst läuft die App auf der CPU.
pyinstaller packaging\gideons_uebersetzer.spec --clean --noconfirm --distpath packaging\dist
:: Inno Setup 6 öffnen und packaging\installer.iss kompilieren
:: -> packaging\dist\Tolino-Uebersetzer-Setup-<Version>.exe
```

Alternativ lokal alles auf einmal: `packaging\build-windows.bat`.
Automatisch baut die GitHub-Action `.github/workflows/build-windows.yml` den Installer
bei jedem Push auf `main` (Artefakt + Draft-Release `latest-build`) bzw. bei Tag `v*`
als veröffentlichten Release.

Kontrolle: `packaging\\dist\\Gideons-Uebersetzer\\Gideons-Uebersetzer.exe` startet ohne Python auf dem Testrechner
(kein Konsolenfenster, Hauptfenster erscheint).

## 2. 1-Klick-Beweis (Abnahmekriterium 3)

1. Nur `Tolino-Uebersetzer-Setup-<Version>.exe` ausführen, Standardwerte bestätigen.
2. App starten → Erststart-Assistent erscheint.
3. OFFLINE ist vorausgewählt (erste Stelle). Klick „Weiter“ (1. Klick),
   dann „Modell jetzt laden“ (2. Klick). Download läuft mit Fortschritt,
   Geschwindigkeit und Abbrechen-Knopf; nach Abschluss ist die App betriebsbereit.
4. PDF per Drag & Drop ins Fenster ziehen → „Übersetzen starten“.

## 3. EPUB-Validierung (Abnahmekriterium 1)

- epubcheck: `java -jar epubcheck.jar "<Buch> (deutsch).epub"` → keine Fehler.
- Calibre: EPUB öffnen, Buch durchblättern, Inhaltsverzeichnis prüfen.
- epubcheck-Alternative ohne Java: Strukturprüfung per `tests/` (pytest) oder
  Calibre „Buch bearbeiten".

## 4. Offline-Beweis (Abnahmekriterium 4)

1. Modell einmalig laden (Assistent).
2. Netzwerkkabel ziehen / WLAN trennen.
3. Englisches Buch-PDF (100+ Seiten) vollständig übersetzen lassen → muss
   komplett durchlaufen, EPUB wird geschrieben.

## 5. Fortsetzen nach Abbruch (Abnahmekriterium 5)

1. Übersetzung starten, nach einigen Abschnitten „Abbrechen“.
2. App beenden, neu starten, dasselbe PDF wählen → Frage „Übersetzung
   fortsetzen?“ mit „Ja“ beantworten → 1 Klick, Rest wird übersetzt,
   fertige EPUB entsteht.

## 6. Privatsphäre-Beweis (Abnahmekriterium 6)

- Ohne eingeschalteten Online-Betrieb während einer kompletten Übersetzung die
  Netzwerkaktivität beobachten (z. B. Windows-Ressourcenmonitor oder Wireshark
  auf dem Router): kein ausgehender Datenverkehr mit Buchinhalten.
- Der Online-Betrieb ist in den Einstellungen standardmäßig AUS und lässt sich
  nur bewusst einschalten; der Hinweis („sendet Buchtext an Mistral“) ist im
  Assistenten und in den Einstellungen sichtbar.

## 7. API-Notnagel (Abnahmekriterium 7)

1. Einstellungen → Online-Betrieb einschalten, API-Schlüssel eintragen.
2. Buch übersetzen → Abschluss-Zusammenfassung zeigt „An Mistral gesendete
   Zeichen“ (Kostenschätzung über Mistral-Preise pro 1 Mio. Zeichen).
3. Ohne Schlüssel: klare deutsche Fehlermeldung, kein Traceback.

## 8. Tolino (Abnahmekriterium 2)

- EPUB per USB auf den Tolino kopieren (Ordner „Books“).
- Öffnen: umbruchfähiger Text, funktionierendes Inhaltsverzeichnis,
  Titelseite mit Hinweis „Deutsche Übersetzung, automatisch erstellt“,
  ggf. Deckbild aus der ersten PDF-Seite.

## 9. Fehlerszenarien

- Eingescanntes PDF (nur Bilder) → wird per OCR gelesen (Protokoll: „Seite x/y:
  OCR …“); mit ausgeschaltetem OCR → Meldung: „… keine Textebene … OCR ist
  ausgeschaltet …“. OCR-Pfad auch in der gebauten EXE testen (Scan-PDF komplett
  übersetzen lassen).
- Modell nicht geladen + Offline gewählt → klare Meldung mit Verweis auf „Modell laden“.
- Abgebrochener Modell-Download → „.part“-Datei bleibt liegen, nächster Start
  setzt per Range-Request fort; fertige Datei wird auf Vollständigkeit geprüft.
- Einzelne Abschnitte schlagen fehl (z. B. API-Limit) → bis zu 2 Wiederholungen,
  danach Notiz im EPUB, Buch bleibt lesbar.
