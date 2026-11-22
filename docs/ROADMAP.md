# Roadmap – Ideen für nach Version 1.0

Verfolgt als Issues im Projekt (je Klick öffnet sich der Issue):

- [x] [#3](https://github.com/gschmalzhaf-cell/Gideon-s-bersetzer/issues/3) **OCR für gescannte PDFs** – umgesetzt mit RapidOCR (ONNX, lokal, in der EXE gebündelt): Seiten ohne Textebene werden per OCR erkannt und in denselben Kapitel-/Absatzfluss eingespeist; Einstellung „OCR“ in den Einstellungen, CLI-Flag `--no-ocr`.
- [x] [#1](https://github.com/gschmalzhaf-cell/Gideon-s-bersetzer/issues/1) **EPUB und DOCX als weitere Eingabeformate** – umgesetzt mit v1.2.0: `document_reader.py` (ebooklib für EPUB inkl. Spine-Reihenfolge, python-docx für DOCX; Überschriften werden zu Kapiteln), Drag & Drop und Dateidialog akzeptieren `*.pdf`/`*.epub`/`*.docx`.
- [x] [#2](https://github.com/gschmalzhaf-cell/Gideon-s-bersetzer/issues/2) **Zwei Sprachen nebeneinander im EPUB** – umgesetzt mit v1.4.0: Option „Zweisprachiges EPUB erzeugen“ in den Einstellungen bzw. CLI `--bilingual`, stellt Original- und Übersetzungsabsatz paarweise untereinander dar (`epub_builder.py`).
