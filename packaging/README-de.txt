Gideon's Übersetzer – Kurzanleitung (deutsch)
=============================================

Was macht die App?
------------------
Gideon's Übersetzer liest ein englischsprachiges PDF, übersetzt es ins Deutsche
und erzeugt daraus eine EPUB-Datei, die Sie per USB auf Ihren Tolino laden können.

Erster Start
------------
1. Doppelklick auf „Gideon's Übersetzer".
2. Der Erststart-Assistent begrüßt Sie. Der OFFLINE-Weg ist vorausgewählt
   (empfohlen): Klicken Sie auf „Weiter" und dann auf „Modell jetzt laden".
   Das Übersetzungsmodell (ca. 4–5 GB) wird einmalig von Hugging Face
   heruntergeladen – mit Fortschrittsanzeige und Abbrechen-Knopf. Danach
   läuft alles lokal, ohne Internet. Kein API-Schlüssel nötig.
3. Fertig: Ziehen Sie ein englisches PDF in das Fenster (oder „PDF wählen …")
   und klicken Sie „Übersetzen starten".

Online-Notnagel (optional)
--------------------------
Im Assistenten oder unter „Einstellungen …“ können Sie bewusst auf die
Mistral-API umstellen und Ihren API-Schlüssel eintragen.
ACHTUNG: Dann wird der Buchtext an Mistral (api.mistral.ai) übertragen.
Ohne eingeschalteten Online-Betrieb verlässt kein Buchinhalt Ihr Gerät.

PDF-Anforderungen
------------------
Text-PDFs werden direkt gelesen. Eingescannte PDFs (Seiten nur als Bild) werden
automatisch per OCR erkannt (lokal auf dem Gerät, Einstellung „OCR“ in den
Einstellungen, Standard: an). Nur wenn OCR ausgeschaltet ist, wird eine klare
Meldung angezeigt.

Ergebnis
--------
Die EPUB-Datei landet im gewählten Zielordner, standardmäßig
„<Originaltitel> (deutsch).epub". EPUB 3 ohne Kopierschutz, mit
Inhaltsverzeichnis (nav + NCX), umbruchfähigem Text und deutscher
Typografie (»…«).

Unterbrechen & Fortsetzen
-------------------------
Sie können jederzeit abbrechen. Beim erneuten Öffnen desselben PDFs fragt die
App, ob fortgesetzt werden soll – übersetzte Abschnitte werden nicht doppelt
berechnet.

Einstellungen
--------------
„Einstellungen …“ im Hauptfenster: Werkzeug (Offline/Online), Online-Betrieb
an/aus (Standard: aus), API-Schlüssel und -Modell, Temperatur (Standard 0,3),
Abschnittsgröße (Standard 1500 Wörter), Glossar-Datei („Begriff = Übersetzung"
pro Zeile), Zielordner sowie Modellpfad mit „Modell laden“ / „Modell löschen“
und Speicheranzeige. Alles liegt in settings.json im Benutzerprofil
(%LOCALAPPDATA%\Tolino-Uebersetzer\settings.json); das Modell unter
%LOCALAPPDATA%\Tolino-Uebersetzer\models.

Deinstallieren
---------------
Über „Apps & Features“ in Windows. Dabei bleiben das Modell und die
Einstellungen in %LOCALAPPDATA%\Tolino-Uebersetzer erhalten, sofern Sie sie
nicht manuell löschen.
