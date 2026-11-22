"""Übersetzungs-Pipeline: steuert den Ablauf Abschnitt für Abschnitt.

Wird von der Kommandozeile (M1/M2) und der GUI (M3) gemeinsam verwendet.
- übersetzt Chunk für Chunk mit Stützkontext (letzte 1–2 übersetzte Absätze)
- wiederholt misslungene Abschnitte bis zu zweimal, markiert sie danach als fehlgeschlagen
- sichert jeden Abschnitt sofort im JSON-Zwischenspeicher (Fortsetzen möglich)
- meldet Fortschritt inkl. Seite, Restdauer und Live-Textprobe
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path

from . import epub_builder, intelligence, pdf_reader
from .cache import STATUS_DONE, STATUS_FAILED, TranslationCache
from .pdf_reader import PdfBook
from .translator_base import (
    MAX_RETRIES,
    CancelledError,
    Chunk,
    build_messages,
    load_glossary,
    prompt_format_for,
    quality_check,
    sanitize_translation,
    split_into_chunks,
)


@dataclass
class ProgressInfo:
    done: int
    total: int
    page: int
    chunk_index: int
    elapsed_seconds: float
    eta_seconds: float
    preview: str = ""


@dataclass
class RunResult:
    output_path: Path | None
    pages: int
    words: int
    chunks_total: int
    chunks_done: int
    chunks_failed: int
    duration_seconds: float
    chars_sent: int  # nur im API-Betrieb > 0
    resumed: bool
    cancelled: bool


class PipelineListener:
    """ Rückrufe der Pipeline; die GUI/CLI überschreibt die gewünschten Methoden."""

    def on_start(self, total_chunks: int, resumed: bool) -> None: ...

    def on_chunk_start(self, chunk: Chunk, done: int, total: int) -> None: ...

    def on_token(self, text: str) -> None: ...  # Live-Textprobe

    def on_chunk_done(self, chunk: Chunk, translation: str | None, done: int, total: int, problem: str | None) -> None: ...

    def on_progress(self, info: ProgressInfo) -> None: ...

    def on_log(self, message: str) -> None: ...

    def on_finished(self, result: RunResult) -> None: ...


class TranslationPipeline:
    def __init__(
        self,
        book: PdfBook,
        translator,  # LocalTranslator oder ApiTranslator
        settings,
        cache: TranslationCache,
        listener: PipelineListener | None = None,
        cancel_event: threading.Event | None = None,
        glossary: list[tuple[str, str]] | None = None,
        output_path: str | Path | None = None,
        cover_png: bytes | None = None,
        retry_failed: bool = False,
    ):
        self.book = book
        self.translator = translator
        self.settings = settings
        self.cache = cache
        self.listener = listener or PipelineListener()
        self.cancel_event = cancel_event or threading.Event()
        self.retry_failed = retry_failed
        user_glossary = glossary if glossary is not None else load_glossary(settings.glossary_path)
        self.chunks = split_into_chunks(book.chapters, settings.chunk_size)

        # Automatisches Buch-Glossar (Eigennamen/Orte vorab extrahieren, Nutzer-Glossar hat Vorrang)
        if getattr(settings, "auto_glossary", True):
            auto_entries = intelligence.extract_auto_glossary([c.text for c in self.chunks])
            self.auto_glossary_count = len(auto_entries)
            self.glossary = intelligence.merge_glossaries(user_glossary, auto_entries)
        else:
            self.auto_glossary_count = 0
            self.glossary = list(user_glossary)

        # Ausgangssprache bestimmen (auto -> en/fr/es/it)
        sample_text = " ".join(c.text for c in self.chunks[:2])[:1800]
        self._sample_text = sample_text
        self.source_lang = intelligence.resolve_source_language(
            getattr(settings, "source_lang", "auto"), sample_text
        )
        self.style_profile = getattr(settings, "style_profile", "literary")
        self.bilingual = bool(getattr(settings, "bilingual", False))

        if output_path is None:
            out_dir = settings.resolved_output_dir()
            output_path = out_dir / epub_builder.output_filename(book.title, bilingual=self.bilingual)
        self.output_path = Path(output_path)
        self.cover_png = cover_png

    def _cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def _translate_chunk(self, chunk: Chunk, context: list[str]) -> tuple[str, int]:
        """Ein Chunk inkl. Qualitätsprüfung und Wiederholung. Liefert (Text, gesendete Zeichen)."""
        hint = ""
        last_problem = None
        fmt = prompt_format_for(self.settings)
        relevant_glossary = intelligence.filter_relevant_glossary(self.glossary, chunk.text)
        for attempt in range(1 + MAX_RETRIES):
            if self._cancelled():
                raise CancelledError("Übersetzung abgebrochen.")
            messages = build_messages(
                chunk.text,
                context,
                relevant_glossary,
                extra_hint=hint,
                fmt=fmt,
                style_profile=self.style_profile,
                source_lang=self.source_lang,
            )
            # Wiederholungen deterministisch (Temperatur 0), damit ein einmaliger
            # Aussetzer nicht dreimal reproduziert wird.
            temperature = self.settings.temperature if attempt == 0 else 0.0
            result = self.translator.translate_stream(
                messages,
                temperature=temperature,
                on_token=self.listener.on_token,
                cancel_event=self.cancel_event,
            )
            if isinstance(result, tuple):
                translation, chars = result
            else:
                translation, chars = result, 0
            translation = sanitize_translation(translation)
            problem = quality_check(chunk.text, translation, source_lang=self.source_lang)
            if problem is None:
                return translation, chars
            last_problem = problem
            self.listener.on_log(
                f"Abschnitt {chunk.index + 1}: Qualitätsprüfung fehlgeschlagen ({problem}) – Versuch {attempt + 1} von {1 + MAX_RETRIES}."
            )
            hint = (
                "Antworte ausschließlich mit der reinen deutschen Übersetzung des zu übersetzenden "
                "Textes – ohne Einleitung, ohne „Translation:“-Zeile, ohne Code-Fences und ohne "
                "Anführungszeichen um den gesamten Text. Übersetze JEDEN Satz vollständig ins Deutsche."
            )
        raise ChunkFailedError(last_problem or "Unbekannter Fehler")

    def _translate_chapter_titles(self) -> tuple[dict[int, str], int]:
        """Übersetzt erkannte Kapitelüberschriften gebündelt in einem Aufruf.

        Fällt bei Fehlern oder unvollständigem Format geräuschlos auf die Original-Überschriften zurück.
        """
        indexed = [(i, ch.title.strip()) for i, ch in enumerate(self.book.chapters) if ch.title and ch.title.strip()]
        if not indexed:
            return {}, 0
        block = intelligence.build_headings_block([t for _, t in indexed])
        fmt = prompt_format_for(self.settings)
        hint = (
            "Übersetze jede nummerierte Kapitelüberschrift ins Deutsche und behalte exakt das "
            "Nummerierungsformat '[1] ...', '[2] ...' zeilenweise bei."
        )
        chars_total = 0
        for attempt in range(1 + MAX_RETRIES):
            if self._cancelled():
                raise CancelledError("Übersetzung abgebrochen.")
            messages = build_messages(
                block,
                [],
                self.glossary[:10],
                extra_hint=hint,
                fmt=fmt,
                style_profile=self.style_profile,
                source_lang=self.source_lang,
            )
            try:
                res = self.translator.translate_stream(
                    messages,
                    temperature=0.0,
                    on_token=None,
                    cancel_event=self.cancel_event,
                )
            except CancelledError:
                raise
            except Exception:
                return {}, chars_total
            if isinstance(res, tuple):
                raw, chars = res
            else:
                raw, chars = res, 0
            chars_total += chars
            cleaned = sanitize_translation(raw)
            if not cleaned:
                continue
            parsed = intelligence.parse_translated_headings(cleaned, len(indexed))
            if parsed:
                mapped = {indexed[k][0]: v for k, v in parsed.items()}
                self.listener.on_log(f"{len(mapped)} Kapitelüberschrift(en) automatisch ins Deutsche übersetzt.")
                return mapped, chars_total
            # Fallback: wenn Modell ohne Nummerierung geantwortet hat, aber Zeilenanzahl passt
            lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
            if len(lines) == len(indexed):
                mapped = {indexed[k][0]: lines[k] for k in range(len(indexed))}
                self.listener.on_log(f"{len(mapped)} Kapitelüberschrift(en) automatisch ins Deutsche übersetzt.")
                return mapped, chars_total
            break
        return {}, chars_total

    def run(self) -> RunResult:
        """Führt die Übersetzung aus. Liefert das Ergebnis; wirft CancelledError bei Abbruch."""
        started = time.monotonic()
        total = len(self.chunks)
        translations: dict[int, str | None] = {}
        chars_sent = 0

        # Vorab-Spracherkennung & Hinweise
        if intelligence.is_likely_german(self._sample_text):
            self.listener.on_log(
                "Hinweis: Der Quelltext wirkt bereits überwiegend deutsch – bitte prüfen, ob das richtige Dokument gewählt wurde."
            )
        else:
            lang_name = intelligence.LANGUAGE_NAMES_DE.get(self.source_lang, self.source_lang)
            self.listener.on_log(f"Ausgangssprache: {lang_name} · Stil-Profil: {self.style_profile}")
        if self.auto_glossary_count:
            self.listener.on_log(
                f"Auto-Glossar: {self.auto_glossary_count} wiederkehrende Begriffe/Eigennamen erkannt."
            )

        resumed = any(
            (cached := self.cache.get(c.index)) is not None and cached.status == STATUS_DONE
            for c in self.chunks
        )
        self.listener.on_start(total, resumed)
        self.listener.on_log(
            f"{total} Abschnitte zu übersetzen"
            + (
                " (gezieltes Nachübersetzen fehlgeschlagener Abschnitte)."
                if self.retry_failed
                else (
                    " (Fortsetzung: bereits übersetzte Abschnitte werden aus dem Zwischenspeicher übernommen)."
                    if resumed
                    else "."
                )
            )
        )

        context: list[str] = []
        done = 0
        chunk_times: list[float] = []

        for chunk in self.chunks:
            if self._cancelled():
                raise CancelledError("Übersetzung abgebrochen.")
            cached = self.cache.get(chunk.index)
            if cached is not None:
                if cached.status == STATUS_DONE:
                    translations[chunk.index] = cached.translation
                    context.extend(p for p in cached.translation.split("\n\n") if p.strip())
                    done += 1
                    continue
                if cached.status == STATUS_FAILED and not self.retry_failed:
                    translations[chunk.index] = None
                    done += 1
                    continue

            self.listener.on_chunk_start(chunk, done, total)
            chunk_started = time.monotonic()
            translation: str | None = None
            problem: str | None = None
            try:
                translation, chars = self._translate_chunk(chunk, context)
                chars_sent += chars
                self.cache.record(chunk.index, chunk.text, translation, STATUS_DONE)
                translations[chunk.index] = translation
                context.extend(p for p in translation.split("\n\n") if p.strip())
            except CancelledError:
                raise
            except ChunkFailedError as exc:
                problem = str(exc)
                self.cache.record(chunk.index, chunk.text, "", STATUS_FAILED, problem=problem)
                translations[chunk.index] = None
                self.listener.on_log(
                    f"Abschnitt {chunk.index + 1} konnte nach {1 + MAX_RETRIES} Versuchen nicht übersetzt werden "
                    f"({problem}). Er wird im EPUB mit einer Notiz versehen."
                )
            except Exception as exc:
                problem = str(exc) or exc.__class__.__name__
                self.cache.record(chunk.index, chunk.text, "", STATUS_FAILED, problem=problem)
                translations[chunk.index] = None
                self.listener.on_log(
                    f"Abschnitt {chunk.index + 1} ist fehlgeschlagen ({problem}). Er wird im EPUB mit einer Notiz versehen."
                )
            finally:
                chunk_times.append(time.monotonic() - chunk_started)
                done += 1
                elapsed = time.monotonic() - started
                remaining = total - done
                eta = (sum(chunk_times) / len(chunk_times) * remaining) if chunk_times and remaining else 0.0
                self.listener.on_chunk_done(chunk, translation, done, total, problem)
                self.listener.on_progress(
                    ProgressInfo(
                        done=done,
                        total=total,
                        page=chunk.page,
                        chunk_index=chunk.index,
                        elapsed_seconds=elapsed,
                        eta_seconds=eta,
                    )
                )

        if self._cancelled():
            raise CancelledError("Übersetzung abgebrochen.")

        chapter_titles_de, heading_chars = self._translate_chapter_titles()
        chars_sent += heading_chars

        first_idx = next((i for i, ch in enumerate(self.book.chapters) if ch.title), None)
        title_de = (
            chapter_titles_de.get(first_idx)
            if first_idx is not None
            else None
        ) or self.book.first_chapter_title or self.book.title

        result = epub_builder.build_epub(
            self.book,
            self.chunks,
            translations,
            self.output_path,
            title_de=title_de,
            cover_png=self.cover_png,
            chapter_titles_de=chapter_titles_de,
            bilingual=self.bilingual,
        )
        if result.failed_chunks == 0:
            self.cache.clear()
        else:
            self.listener.on_log(
                f"Zwischenspeicher für {result.failed_chunks} fehlgeschlagene(n) Abschnitt(e) behalten – "
                "gezieltes Nachübersetzen möglich."
            )
        run_result = RunResult(
            output_path=result.path,
            pages=self.book.page_count,
            words=self.book.word_count,
            chunks_total=total,
            chunks_done=sum(1 for v in translations.values() if v is not None),
            chunks_failed=result.failed_chunks,
            duration_seconds=time.monotonic() - started,
            chars_sent=chars_sent,
            resumed=resumed,
            cancelled=False,
        )
        self.listener.on_finished(run_result)
        return run_result


class ChunkFailedError(Exception):
    """Ein Abschnitt blieb nach allen Versuchen ohne brauchbares Ergebnis."""
