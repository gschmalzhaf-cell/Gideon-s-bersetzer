Gideon's Übersetzer – Kurzanleitung (deutsch)
=============================================

Was macht die App?
------------------
Gideon's Übersetzer liest englischsprachige Bücher und Dokumente (PDF, EPUB, DOCX),
übersetzt sie vollständig ins Deutsche und erzeugt daraus eine fertige EPUB-Datei
für Ihren Tolino-E-Book-Reader.

Erster Start & Bedienung in 3 Schritten
---------------------------------------
1. Doppelklick auf „Gideon's Übersetzer".
2. Beim ersten Start führt Sie der Assistent durch die Einrichtung. Der OFFLINE-Weg
   ist vorausgewählt (empfohlen): Klicken Sie auf „Weiter" und auf „Modell jetzt laden".
   Das Sprachmodell (Standard: Qwen2.5-7B-Instruct, ca. 4,7 GB) wird einmalig von
   Hugging Face geladen – danach läuft alles lokal ohne Internet und ohne API-Schlüssel.
3. Im Hauptfenster folgt alles einer klaren 3-Schritte-Struktur:
   • Schritt 1 (Dokumente auswählen): Ein oder mehrere Bücher (PDF, EPUB, DOCX) per
     Drag & Drop in die Warteschlange ziehen oder über „+ Dokumente hinzufügen …" wählen.
   • Schritt 2 (Ausgabe & Modus): Zielordner prüfen (direkt per „Ordner öffnen"
     einsehbar), optional ein eigenes Glossar angeben.
   • Schritt 3 (Übersetzung & Live-Einblick): „Übersetzen starten" klicken. Unten
     sehen Sie in zwei Reitern die „Live-Textprobe" des aktuellen Abschnitts sowie
     „Protokoll & Details".

Kuscheliges Design
------------------
Die Oberfläche und der Installer passen sich im Modus „Automatisch – kuschelig-saisonal"
der Jahreszeit an (Herbst, Winter, Frühling, Sommer). In den Einstellungen können Sie
auch fest „Hell" oder „Dunkel (kuschelig)" wählen.

Online-Notnagel (optional)
--------------------------
Im Assistenten oder unter „Einstellungen … → Allgemein & Modus" können Sie bewusst
auf die Mistral-API umstellen und Ihren API-Schlüssel eintragen.
ACHTUNG: Dann wird der Buchtext an Mistral (api.mistral.ai) übertragen.
Ohne eingeschalteten Online-Betrieb verlässt kein Buchinhalt Ihr Gerät.

Einstellungen (3 Reiter)
------------------------
• Allgemein & Modus: Design (saisonal / hell / dunkel), Zielordner, Glossar-Datei,
  Werkzeug (Offline / Mistral-API) und Online-Schutz.
• Offline-Modell: Auswahl zwischen Qwen2.5-7B-Instruct (empfohlen, 4,7 GB),
  TranslateGemma-12B-IT (6,8 GB) und TranslateGemma-4B-IT (2,3 GB), Speicherstatus,
  Modell laden/löschen sowie Erststart-Assistent.
• Qualität & OCR: Temperatur (Standard 0,3), Wörter pro Abschnitt (Standard 1500),
  automatische Texterkennung (OCR) für gescannte PDF-Seiten (Standard: lokal per RapidOCR).

Unterbrechen & Fortsetzen
-------------------------
Sie können jederzeit abbrechen. Beim erneuten Start derselben Datei fragt die App,
ob aus dem Zwischenspeicher fortgesetzt werden soll.

Deinstallieren
--------------
Über „Apps & Features" in Windows. Dabei bleiben das heruntergeladene Modell und
die Einstellungen unter %LOCALAPPDATA%\Tolino-Uebersetzer erhalten.

