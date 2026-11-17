import threading

import pytest

from gideons_uebersetzer import pdf_reader, settings as settings_mod
from gideons_uebersetzer.cache import STATUS_DONE, STATUS_FAILED, TranslationCache
from gideons_uebersetzer.pipeline import (
    CancelledError,
    PipelineListener,
    TranslationPipeline,
)
from gideons_uebersetzer.translator_base import CancelledError as BaseCancelled


class ScriptedTranslator:
    """Übersetzt auf Basis des erkannten Quelltexts (enthält 'Abschnitt N')."""

    _streams = True

    def __init__(self, behavior="ok"):
        self.behavior = behavior
        self.attempts: dict[str, int] = {}
        self.sent_chars = 0

    def translate_stream(self, messages, temperature, on_token=None, cancel_event=None):
        source = messages[1]["content"]
        self.sent_chars += len(source)
        key = source.split('"""')[1]  # nur der Quelltext, unabhängig vom Retry-Hinweis
        self.attempts[key] = self.attempts.get(key, 0) + 1
        if cancel_event is not None and cancel_event.is_set():
            raise BaseCancelled()
        n = self.attempts[key]
        if self.behavior == "always_fail":
            return "Hier ist die Übersetzung: kaputt", 0
        if self.behavior == "fail_twice":
            if n <= 2:
                return "", 0  # leere Antwort -> Qualitätsprüfung schlägt fehl
        if "Abschnitt 1" in source and self.behavior == "short":
            return "kurz", 0
        text = ("Deutscher Übersetzungstext für diesen Abschnitt. " * 12)[:400]
        if on_token:
            on_token(text[:50])
            on_token(text[50:])
        return text, self.sent_chars


def _make_pipeline(tmp_path, sample_pdf, translator, cache=None, listener=None):
    book = pdf_reader.extract_book(sample_pdf)
    s = settings_mod.Settings(chunk_size=40, output_dir=str(tmp_path))
    if cache is None:
        cache = TranslationCache(sample_pdf, TranslationCache.cache_file_for(sample_pdf, tmp_path))
    pipe = TranslationPipeline(
        book=book,
        translator=translator,
        settings=s,
        cache=cache,
        listener=listener or PipelineListener(),
        cancel_event=threading.Event(),
    )
    return pipe, book


def test_pipeline_full_run(tmp_path, sample_pdf):
    pipe, book = _make_pipeline(tmp_path, sample_pdf, ScriptedTranslator())
    result = pipe.run()
    assert result.output_path.is_file()
    assert result.chunks_failed == 0
    assert result.chunks_done == result.chunks_total
    assert result.pages == book.page_count
    assert result.words == book.word_count
    assert result.duration_seconds >= 0
    assert result.chars_sent > 0  # Zeichenzählung (API-Betrieb) läuft mit
    # Zwischenspeicher wurde nach erfolgreichem Lauf geleert
    assert not pipe.cache.cache_file.exists()


def test_pipeline_retries_then_succeeds(tmp_path, sample_pdf):
    pipe, _ = _make_pipeline(tmp_path, sample_pdf, ScriptedTranslator("fail_twice"))
    result = pipe.run()
    assert result.chunks_failed == 0
    # jeder Chunk wurde 3x versucht (2 Fehlschläge + Erfolg)
    assert all(n == 3 for n in pipe.translator.attempts.values())


def test_pipeline_marks_failed_after_retries(tmp_path, sample_pdf):
    listener = PipelineListener()
    pipe, _ = _make_pipeline(tmp_path, sample_pdf, ScriptedTranslator("always_fail"), listener=listener)
    result = pipe.run()
    assert result.chunks_failed == result.chunks_total
    assert result.chunks_done == 0
    # Notiz landet im EPUB
    import zipfile

    with zipfile.ZipFile(result.output_path) as zf:
        all_html = b"".join(zf.read(n) for n in zf.namelist() if n.endswith(".xhtml"))
    assert "konnte nicht übersetzt werden" in all_html.decode("utf-8")


def test_pipeline_resume_from_cache(tmp_path, sample_pdf):
    cache = TranslationCache(sample_pdf, TranslationCache.cache_file_for(sample_pdf, tmp_path), tool="offline")
    # ersten Lauf: bricht nach dem ersten Chunk ab
    pipe, book = _make_pipeline(tmp_path, sample_pdf, ScriptedTranslator(), cache=cache)

    orig_run = pipe.run

    class CancellingListener(PipelineListener):
        def __init__(self):
            self.count = 0

        def on_chunk_done(self, chunk, translation, done, total, problem):
            self.count += 1
            if self.count == 1:
                pipe.cancel_event.set()

    listener = CancellingListener()
    pipe.listener = listener
    with pytest.raises(CancelledError):
        pipe.run()
    assert cache.cache_file.is_file()
    assert cache.done_count == 1

    # zweiter Lauf: lädt Cache, übersetzt den Rest
    loaded = TranslationCache.load(sample_pdf, base_dir=tmp_path)
    assert loaded is not None and loaded.done_count == 1
    pipe2, _ = _make_pipeline(tmp_path, sample_pdf, ScriptedTranslator(), cache=loaded)
    result = pipe2.run()
    assert result.resumed is True
    assert result.chunks_done == result.chunks_total
    assert result.output_path.is_file()


def test_pipeline_cancel_via_event(tmp_path, sample_pdf):
    pipe, _ = _make_pipeline(tmp_path, sample_pdf, ScriptedTranslator())
    pipe.cancel_event.set()
    with pytest.raises(CancelledError):
        pipe.run()


def test_pipeline_sanitizes_marker_answers(tmp_path, sample_pdf):
    class MarkerTranslator:
        def translate_stream(self, messages, temperature, on_token=None, cancel_event=None):
            text = ("Deutscher Übersetzungstext für diesen Abschnitt. " * 12)[:400]
            return f'Translation:\n"""\n{text}\n"""', 0

    pipe, _book = _make_pipeline(tmp_path, sample_pdf, MarkerTranslator())
    result = pipe.run()
    assert result.chunks_failed == 0
    assert result.chunks_done == result.chunks_total


def test_pipeline_retry_uses_temperature_zero(tmp_path, sample_pdf):
    temps = []

    class FlakyTranslator:
        def __init__(self):
            self.n = 0

        def translate_stream(self, messages, temperature, on_token=None, cancel_event=None):
            temps.append(temperature)
            self.n += 1
            if self.n == 1:
                return "", 0  # leere Antwort -> Qualitätsprüfung schlägt fehl -> Retry
            return ("Deutscher Text für den Abschnitt. " * 20)[:400], 0

    pipe, _book = _make_pipeline(tmp_path, sample_pdf, FlakyTranslator())
    result = pipe.run()
    assert result.chunks_failed == 0
    assert temps[0] == 0.3  # erster Versuch mit eingestellter Temperatur
    assert temps[1] == 0.0  # Retry deterministisch


def test_pipeline_uses_translategemma_prompt_format(tmp_path, sample_pdf):
    seen = []

    class InspectTranslator:
        def translate_stream(self, messages, temperature, on_token=None, cancel_event=None):
            seen.append(messages)
            return ("Deutscher Text für den Abschnitt. " * 20)[:400], 0

    s = settings_mod.Settings(chunk_size=40, output_dir=str(tmp_path), hf_filename="translategemma-12b-it.Q4_K_M.gguf")
    book = pdf_reader.extract_book(sample_pdf)
    cache = TranslationCache(sample_pdf, TranslationCache.cache_file_for(sample_pdf, tmp_path))
    pipe = TranslationPipeline(book=book, translator=InspectTranslator(), settings=s, cache=cache,
                               listener=PipelineListener(), cancel_event=threading.Event())
    result = pipe.run()
    assert result.chunks_failed == 0
    assert seen and all(m[0]["role"] == "user" and isinstance(m[0]["content"], list) for m in seen)


def test_pipeline_api_mode_uses_plain_string_content(tmp_path, sample_pdf):
    seen = []

    class InspectTranslator:
        def translate_stream(self, messages, temperature, on_token=None, cancel_event=None):
            seen.append(messages)
            return ("Deutscher Text für den Abschnitt. " * 20)[:400], 0

    s = settings_mod.Settings(tool="api", chunk_size=40, output_dir=str(tmp_path), hf_filename="translategemma-12b-it.Q4_K_M.gguf")
    book = pdf_reader.extract_book(sample_pdf)
    cache = TranslationCache(sample_pdf, TranslationCache.cache_file_for(sample_pdf, tmp_path))
    pipe = TranslationPipeline(book=book, translator=InspectTranslator(), settings=s, cache=cache,
                               listener=PipelineListener(), cancel_event=threading.Event())
    result = pipe.run()
    assert result.chunks_failed == 0
    assert seen and all(len(m) == 2 and m[0]["role"] == "system" for m in seen)
    assert all(isinstance(m[1]["content"], str) for m in seen)
