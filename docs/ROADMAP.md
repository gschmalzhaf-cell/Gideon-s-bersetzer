# Roadmap – Ideen für nach Version 1.0

Verfolgt als Issues im Projekt (je Klick öffnet sich der Issue):

- [ ] [#3](https://github.com/gschmalzhaf-cell/Gideon-s-bersetzer/issues/3) **OCR für gescannte PDFs (Tesseract-Baustein)** – aktuell bricht die App bei reinen Bild-PDFs mit einer klaren Meldung ab („OCR ist in Version 1 nicht enthalten“). Geplant: Tesseract/ONNX-OCR als optionaler Baustein, der erkannte Seiten in denselben Kapitel-/Absatzfluss einspeist.
- [ ] [#1](https://github.com/gschmalzhaf-cell/Gideon-s-bersetzer/issues/1) **EPUB und DOCX als weitere Eingabeformate** – `translator_base`/`pipeline` arbeiten bereits auf Kapitel + Absätzen (nicht auf PDF); nur der Import fehlt. Geplant: allgemeiner `document_reader.py` (ebooklib für EPUB, python-docx für DOCX), Drag & Drop und Dateidialog um `*.epub`/`*.docx` erweitern.
- [ ] [#2](https://github.com/gschmalzhaf-cell/Gideon-s-bersetzer/issues/2) **Zwei Sprachen nebeneinander im EPUB** (Original Englisch + Übersetzung Deutsch), z. B. zum Vergleichen beim Lesen – als Einstellung „Zweisprachig ausgeben“ in `epub_builder.py`.
