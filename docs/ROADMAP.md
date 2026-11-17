# Roadmap – Ideen für nach Version 1.0

Verfolgt als Issues im Projekt (je Klick öffnet sich der Issue):

- [x] [#3](https://github.com/gschmalzhaf-cell/Gideon-s-bersetzer/issues/3) **OCR für gescannte PDFs** – umgesetzt mit RapidOCR (ONNX, lokal, in der EXE gebündelt): Seiten ohne Textebene werden per OCR erkannt und in denselben Kapitel-/Absatzfluss eingespeist; Einstellung „OCR“ in den Einstellungen, CLI-Flag `--no-ocr`.
- [x] [#1](https://github.com/gschmalzhaf-cell/Gideon-s-bersetzer/issues/1) **EPUB und DOCX als weitere Eingabeformate** – umgesetzt mit v1.2.0: `document_reader.py` (ebooklib für EPUB inkl. Spine-Reihenfolge, python-docx für DOCX; Überschriften werden zu Kapiteln), Drag & Drop und Dateidialog akzeptieren `*.pdf`/`*.epub`/`*.docx`.
- [ ] [#2](https://github.com/gschmalzhaf-cell/Gideon-s-bersetzer/issues/2) **Zwei Sprachen nebeneinander im EPUB** (Original Englisch + Übersetzung Deutsch), z. B. zum Vergleichen beim Lesen – als Einstellung „Zweisprachig ausgeben“ in `epub_builder.py`.
