"""Tests für die intelligenten Funktionen (intelligence.py, PDF-Bereinigung,
Satzgrenzen-Chunking, Überlängen-Check, Kapitelüberschriften-Übersetzung)."""

from __future__ import annotations

import threading
import zipfile
from pathlib import Path

import pymupdf

from gideons_uebersetzer import epub_builder, intelligence, pdf_reader, settings as settings_mod
from gideons_uebersetzer.cache import TranslationCache
from gideons_uebersetzer.pdf_reader import Chapter, Paragraph, _join_lines
from gideons_uebersetzer.pipeline import PipelineListener, TranslationPipeline
from gideons_uebersetzer.translator_base import quality_check, split_into_chunks


def test_detect_language_german_and_english():
    de = (
        "Es war einmal ein kleiner Junge, der in einem großen Haus am Waldrand wohnte. "
        "Er ging jeden Morgen durch den Wald und hörte den Vögeln zu."
    )
    en = (
        "Once upon a time there was a young boy who lived in a large house near the forest. "
        "Every morning he walked through the woods and listened to the birds."
    )
    assert intelligence.detect_language(de) == "de"
    assert intelligence.is_likely_german(de) is True
    assert intelligence.detect_language(en) == "en"
    assert intelligence.is_likely_german(en) is False
    assert intelligence.detect_language("short text") == "unknown"


def test_recommend_model_preset_by_hardware():
    low = intelligence.recommend_model_preset(ram_gb=6.0, has_gpu=False)
    assert low.preset_id == "translategemma-4b"
    assert "6 GB" in low.reason

    mid = intelligence.recommend_model_preset(ram_gb=16.0, has_gpu=False)
    assert mid.preset_id == "qwen2.5-7b"

    high_gpu = intelligence.recommend_model_preset(ram_gb=32.0, has_gpu=True)
    assert high_gpu.preset_id == "translategemma-12b"
    assert "GPU" in high_gpu.reason


def test_filter_relevant_glossary_small_and_large():
    small = [("London", "London"), ("King", "König")]
    assert intelligence.filter_relevant_glossary(small, "Nothing matches here.") == small

    large = [(f"Term{i}", f"Begriff{i}") for i in range(15)] + [("Sherlock Holmes", "Sherlock Holmes")]
    filtered = intelligence.filter_relevant_glossary(large, "Yesterday Sherlock Holmes met Term3 in the fog.")
    assert ("Sherlock Holmes", "Sherlock Holmes") in filtered
    assert ("Term3", "Begriff3") in filtered
    assert ("Term1", "Begriff1") not in filtered


def test_headings_block_and_parser():
    block = intelligence.build_headings_block(["Chapter 1: Dawn", "Chapter 2: Night"])
    assert "[1] Chapter 1: Dawn" in block
    assert "[2] Chapter 2: Night" in block

    parsed = intelligence.parse_translated_headings("[1] Kapitel 1: Morgengrauen\n[2] Kapitel 2: Nacht", 2)
    assert parsed == {0: "Kapitel 1: Morgengrauen", 1: "Kapitel 2: Nacht"}


def test_pdf_hyphenation_repair():
    assert _join_lines(["This is a transla-", "tion example."]) == "This is a translation example."
    assert _join_lines(["A well-", "Known author"]) == "A well- Known author"
    assert _join_lines(["soft\xad", "break"]) == "soft break"


def test_pdf_running_header_and_footer_removed(tmp_path):
    pdf_path = tmp_path / "headers.pdf"
    doc = pymupdf.open()
    for page_nr in range(1, 5):
        page = doc.new_page()
        page.insert_text((72, 40), f"RUNNING BOOK TITLE  {page_nr}", fontsize=9)
        page.insert_text(
            (72, 120),
            f"This is the unique body text on page {page_nr} with enough words to read.",
            fontsize=12,
        )
        page.insert_text((72, 760), "Publisher Footer 2026", fontsize=9)
    doc.save(pdf_path)
    doc.close()

    book = pdf_reader.extract_book(pdf_path)
    all_text = " ".join(p.text for c in book.chapters for p in c.paragraphs)
    assert "RUNNING BOOK TITLE" not in all_text
    assert "Publisher Footer 2026" not in all_text
    assert "unique body text on page 1" in all_text
    assert "unique body text on page 4" in all_text


def test_split_into_chunks_splits_oversized_paragraph_at_sentences():
    long_para = " ".join(f"Sentence number {i} contains several words for testing." for i in range(60))
    chapters = [Chapter(title="One", paragraphs=[Paragraph(long_para, 1)])]
    chunks = split_into_chunks(chapters, 200)
    assert len(chunks) >= 2
    assert all(c.text.endswith(".") for c in chunks)


def test_quality_check_detects_overlong_hallucination():
    src = "The quick brown fox jumps over the lazy dog in the quiet forest. " * 4
    hallucinated = "Der schnelle braune Fuchs springt über den faulen Hund im ruhigen Wald. " * 20
    assert quality_check(src, hallucinated) is not None


def test_pipeline_translates_chapter_titles_into_epub(tmp_path, sample_pdf):
    class HeadingAwareTranslator:
        def translate_stream(self, messages, temperature, on_token=None, cancel_event=None):
            prompt = messages[1]["content"]
            if "[1]" in prompt:
                return "[1] Kapitel 1: Der Anfang\n[2] Kapitel 2: Die Reise", 40
            return ("Deutscher Übersetzungstext für diesen Abschnitt. " * 10)[:350], 100

    book = pdf_reader.extract_book(sample_pdf)
    s = settings_mod.Settings(chunk_size=40, output_dir=str(tmp_path))
    cache = TranslationCache(sample_pdf, TranslationCache.cache_file_for(sample_pdf, tmp_path))
    pipe = TranslationPipeline(
        book=book,
        translator=HeadingAwareTranslator(),
        settings=s,
        cache=cache,
        listener=PipelineListener(),
        cancel_event=threading.Event(),
    )
    result = pipe.run()
    assert result.chunks_failed == 0
    with zipfile.ZipFile(result.output_path) as zf:
        all_xml = "\n".join(zf.read(n).decode("utf-8", errors="ignore") for n in zf.namelist() if n.endswith((".xhtml", ".ncx")))
    assert "Kapitel 1: Der Anfang" in all_xml


def test_summarize_queue(tmp_path):
    f1 = tmp_path / "a.pdf"
    f1.write_bytes(b"1234567890")
    missing = tmp_path / "missing.pdf"
    summary = intelligence.summarize_queue([f1, missing], cache_loader=lambda p: object() if p == f1 else None)
    assert summary.file_count == 2
    assert summary.total_bytes == 10
    assert summary.cached_count == 1
    assert summary.missing_count == 1


def test_detect_language_french_spanish_italian():
    fr = "Il était une fois un petit garçon qui habitait dans une grande maison près de la forêt avec ses amis."
    es = "Había una vez un niño pequeño que vivía en una casa grande cerca del bosque con sus amigos y su familia."
    it = "C'era una volta un piccolo ragazzo che viveva in una grande casa vicino alla foresta con i suoi amici."
    assert intelligence.detect_language(fr) == "fr"
    assert intelligence.detect_language(es) == "es"
    assert intelligence.detect_language(it) == "it"
    assert intelligence.resolve_source_language("auto", fr) == "fr"
    assert intelligence.resolve_source_language("es", fr) == "es"


def test_extract_auto_glossary_and_merge():
    texts = [
        "Yesterday Sherlock Holmes walked down Baker Street with Watson.",
        "Later Sherlock Holmes returned to Baker Street in the rain.",
        "Everyone knew Sherlock Holmes lived on Baker Street near London.",
    ]
    auto = intelligence.extract_auto_glossary(texts, min_occurrences=3)
    terms = [t for t, _ in auto]
    assert "Sherlock Holmes" in terms
    assert "Baker Street" in terms
    # Nutzer-Glossar hat immer Vorrang
    merged = intelligence.merge_glossaries([("Baker Street", "Bäckerstraße")], auto)
    assert dict(merged)["Baker Street"] == "Bäckerstraße"
    assert dict(merged)["Sherlock Holmes"] == "Sherlock Holmes"


def test_style_profiles_and_multilang_prompts():
    from gideons_uebersetzer.translator_base import build_messages, build_system_prompt

    p_tech = build_system_prompt("technical", "fr")
    assert "französischen" in p_tech
    assert "Fachbegriffe" in p_tech

    p_nonf = build_system_prompt("nonfiction", "es")
    assert "spanischen" in p_nonf
    assert "Sachbuch" in p_nonf

    msgs = build_messages("Bonjour le monde.", [], [], fmt="translategemma", style_profile="technical", source_lang="fr")
    assert msgs[0]["content"][0]["source_lang_code"] == "fr"
    assert "Fachbuch" in msgs[0]["content"][0]["text"]

    # Französische Stoppwort-Prüfung
    fr_untranslated = "Le petit prince est dans la maison avec ses amis pour la nuit et il était très heureux."
    assert quality_check(fr_untranslated, fr_untranslated, source_lang="fr") is not None


def test_bilingual_epub_output(tmp_path, sample_pdf):
    book = pdf_reader.extract_book(sample_pdf)
    chunks = split_into_chunks(book.chapters, 60)
    translations = {c.index: f"Übersetzter Abschnitt {c.index}." for c in chunks}
    out = tmp_path / epub_builder.output_filename(book.title, bilingual=True)
    assert out.name.endswith("(zweisprachig).epub")
    res = epub_builder.build_epub(book, chunks, translations, out, bilingual=True)
    assert res.path.is_file()
    with zipfile.ZipFile(res.path) as zf:
        chap0 = zf.read("EPUB/chap_0.xhtml").decode("utf-8")
        title = zf.read("EPUB/titlepage.xhtml").decode("utf-8")
    assert 'class="bilingual-pair"' in chap0
    assert 'class="source-para"' in chap0
    assert 'class="target-para"' in chap0
    assert "Zweisprachige Ausgabe" in title


def test_pipeline_retry_failed_only(tmp_path, sample_pdf):
    calls = []

    class FirstFailChunk0Translator:
        def __init__(self, fail_first_chunk: bool):
            self.fail_first_chunk = fail_first_chunk

        def translate_stream(self, messages, temperature, on_token=None, cancel_event=None):
            prompt = messages[1]["content"]
            calls.append(prompt)
            if self.fail_first_chunk and len(calls) <= 3:
                return "", 0  # Chunk 0 schlägt 3x fehl
            return ("Deutscher Übersetzungstext für diesen Abschnitt. " * 10)[:350], 50

    book = pdf_reader.extract_book(sample_pdf)
    s = settings_mod.Settings(chunk_size=40, output_dir=str(tmp_path))
    cache_file = TranslationCache.cache_file_for(sample_pdf, tmp_path)
    cache = TranslationCache(sample_pdf, cache_file)

    # Lauf 1: Chunk 0 schlägt fehl -> Cache bleibt erhalten!
    pipe1 = TranslationPipeline(
        book=book, translator=FirstFailChunk0Translator(True), settings=s, cache=cache,
        listener=PipelineListener(), cancel_event=threading.Event(),
    )
    res1 = pipe1.run()
    assert res1.chunks_failed == 1
    assert cache_file.is_file()

    # Lauf 2: gezielt nur fehlgeschlagene nachübersetzen -> erledigte Chunks werden nicht neu übersetzt
    calls.clear()
    loaded = TranslationCache.load(sample_pdf, base_dir=tmp_path)
    assert loaded is not None and loaded.failed_count == 1
    pipe2 = TranslationPipeline(
        book=book, translator=FirstFailChunk0Translator(False), settings=s, cache=loaded,
        listener=PipelineListener(), cancel_event=threading.Event(), retry_failed=True,
    )
    res2 = pipe2.run()
    assert res2.chunks_failed == 0
    assert res2.chunks_done == res2.chunks_total
    # Nur 1 fehlgeschlagener Chunk + ggf. 1 Kapitelüberschriften-Aufruf
    assert len(calls) <= 2
    assert not cache_file.exists()  # jetzt komplett -> Cache wird geleert

