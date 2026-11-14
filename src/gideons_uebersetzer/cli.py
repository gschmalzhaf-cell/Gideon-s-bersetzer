"""Kommandozeile (M1: Offline; M2: zusätzlich Mistral-API-Notnagel).

Beispiele:
    python -m gideons_uebersetzer modell laden
    python -m gideons_uebersetzer modell info
    python -m gideons_uebersetzer modell loeschen
    python -m gideons_uebersetzer uebersetzen buch.pdf
    python -m gideons_uebersetzer uebersetzen buch.pdf --tool api --api-key ...
"""

from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path

from . import model_manager, pdf_reader, settings as settings_mod
from .cache import TranslationCache
from .pipeline import CancelledError, PipelineListener, TranslationPipeline
from .translator_base import load_glossary


def _fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h} h {m} min"
    if m:
        return f"{m} min {s} s"
    return f"{s} s"


class CliListener(PipelineListener):
    def __init__(self):
        self._preview = ""

    def on_start(self, total_chunks: int, resumed: bool) -> None:
        print(f"Abschnitte gesamt: {total_chunks}" + (" (Fortsetzung aus Zwischenspeicher)" if resumed else ""))

    def on_chunk_start(self, chunk, done: int, total: int) -> None:
        self._preview = ""
        print(f"[{done + 1}/{total}] Abschnitt ab Seite {chunk.page} ({chunk.word_count} Wörter) …", flush=True)

    def on_token(self, text: str) -> None:
        self._preview += text
        if len(self._preview) > 200:
            self._preview = self._preview[-200:]

    def on_chunk_done(self, chunk, translation, done: int, total: int, problem) -> None:
        if problem:
            print(f"  → fehlgeschlagen ({problem}) – Notiz im EPUB.")
        else:
            probe = (translation or "").replace("\n", " ")[:100]
            print(f"  → ok: {probe}…")

    def on_progress(self, info: ProgressInfo) -> None:
        print(
            f"  Fortschritt {info.done}/{info.total} – Seite {info.page} – "
            f"verstrichen {_fmt_duration(info.elapsed_seconds)}, geschätzt noch {_fmt_duration(info.eta_seconds)}",
            flush=True,
        )

    def on_log(self, message: str) -> None:
        print(f"  Hinweis: {message}")

    def on_finished(self, result) -> None:
        print("Fertig.")


def _cmd_modell(args) -> int:
    settings = settings_mod.load_settings()
    model_path = settings.resolved_model_path()
    if args.modell_cmd == "info":
        if model_manager.is_model_present(model_path):
            print(f"Modell vorhanden: {model_path} ({model_manager.format_bytes(model_manager.model_disk_usage(model_path))})")
        else:
            print(f"Kein Modell installiert unter: {model_path}")
            try:
                info = model_manager.model_file_info(settings.hf_repo, settings.hf_filename)
                print(f"Verfügbar zum Download: {settings.hf_repo}/{settings.hf_filename} "
                      f"({model_manager.format_bytes(info['size'])})")
            except model_manager.ModelError as exc:
                print(f"Konnte Modell-Informationen nicht abrufen: {exc}")
        free = model_manager.free_space_bytes(model_path.parent if model_path.parent.exists() else Path.home())
        print(f"Freier Speicherplatz: {model_manager.format_bytes(free)}")
        return 0
    if args.modell_cmd == "loeschen":
        freed = model_manager.delete_model(model_path)
        print(f"Modell gelöscht. Freigegeben: {model_manager.format_bytes(freed)}")
        return 0
    if args.modell_cmd == "laden":
        cancel = threading.Event()
        try:
            dest = model_manager.download_model(
                settings.hf_repo,
                settings.hf_filename,
                model_path.parent,
                progress_cb=lambda done, total, speed: print(
                    f"\r  {model_manager.format_bytes(done)} / {model_manager.format_bytes(total)} "
                    f"({model_manager.format_bytes(speed)}/s)",
                    end="",
                    flush=True,
                ),
                cancel_event=cancel,
            )
        except KeyboardInterrupt:
            print("\nDownload abgebrochen. Die bereits geladenen Daten bleiben erhalten und werden beim nächsten Start fortgesetzt.")
            return 130
        except model_manager.ModelError as exc:
            print(f"Fehler: {exc}")
            return 1
        print(f"\nModell vollständig geladen: {dest}")
        return 0
    return 2


def _build_translator(args, settings):
    tool = args.tool or settings.tool
    if tool == "api":
        if not settings.online_enabled and not args.online:
            print("Der Online-Betrieb ist ausgeschaltet. Der Buchtext würde an Mistral übertragen. "
                  "Bitte in den Einstellungen bewusst einschalten oder hier mit --online bestätigen.")
            return None
        from .translator_api import ApiError, ApiTranslator

        key = args.api_key or settings.api_key
        try:
            return ApiTranslator(key, args.api_model or settings.api_model, settings.api_endpoint, settings.temperature), "api"
        except ApiError as exc:
            print(f"Fehler: {exc}")
            return None
    from .translator_local import LocalTranslator

    model_path = Path(args.model) if args.model else settings.resolved_model_path()
    try:
        translator = LocalTranslator(model_path)
    except FileNotFoundError as exc:
        print(f"Fehler: {exc}")
        print("Tipp: Modell zuerst laden mit: python -m gideons_uebersetzer modell laden")
        return None
    if translator.gpu_warning:
        print(f"Warnung: {translator.gpu_warning}")
    return translator, "offline"


def _cmd_uebersetzen(args) -> int:
    settings = settings_mod.load_settings()
    if args.output_dir:
        settings.output_dir = args.output_dir
    if args.glossar:
        settings.glossary_path = args.glossar
    if args.chunk_size:
        settings.chunk_size = args.chunk_size
    if args.temperature is not None:
        settings.temperature = args.temperature

    try:
        book = pdf_reader.extract_book(args.pdf)
    except pdf_reader.PdfError as exc:
        print(f"Fehler: {exc}")
        return 1
    print(f"PDF geladen: {book.title} – {book.page_count} Seiten, {book.word_count} Wörter, "
          f"{len(book.chapters)} Kapitel erkannt.")

    built = _build_translator(args, settings)
    if built is None:
        return 1
    translator, tool = built

    cache = TranslationCache.load(args.pdf)
    if cache is not None and not args.no_resume:
        answer = input("Es existiert ein Zwischenspeicher für dieses PDF. Übersetzung fortsetzen? [J/n] ")
        if answer.strip().lower() not in ("", "j", "ja", "y", "yes"):
            cache = None
    if cache is None:
        cache = TranslationCache(args.pdf, TranslationCache.cache_file_for(args.pdf), tool=tool)

    cover = None
    if not args.no_cover:
        cover = pdf_reader.extract_cover_png(args.pdf)

    pipeline = TranslationPipeline(
        book=book,
        translator=translator,
        settings=settings,
        cache=cache,
        listener=CliListener(),
        cancel_event=threading.Event(),
        glossary=load_glossary(settings.glossary_path),
        cover_png=cover,
    )
    try:
        result = pipeline.run()
    except CancelledError:
        print("Übersetzung abgebrochen. Zwischenspeicher wurde gesichert – Fortsetzen später möglich.")
        return 130
    except Exception as exc:
        print(f"Fehler: {exc}")
        return 1
    finally:
        if hasattr(translator, "close"):
            translator.close()

    print("\n=== Zusammenfassung ===")
    print(f"Seiten: {result.pages}")
    print(f"Wörter: {result.words}")
    print(f"Abschnitte: {result.chunks_done} übersetzt, {result.chunks_failed} fehlgeschlagen (von {result.chunks_total})")
    print(f"Dauer: {_fmt_duration(result.duration_seconds)}")
    if tool == "api":
        print(f"An Mistral gesendete Zeichen: {result.chars_sent}")
    print(f"Ausgabedatei: {result.output_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gideons-uebersetzer",
        description="Übersetzt englische PDFs ins Deutsche und erzeugt eine EPUB-Datei für den Tolino.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_model = sub.add_parser("modell", help="Offline-Modell verwalten (laden, info, loeschen)")
    p_model.add_argument("modell_cmd", choices=["laden", "info", "loeschen"])
    p_model.set_defaults(func=_cmd_modell)

    p_tr = sub.add_parser("uebersetzen", help="PDF übersetzen und EPUB erzeugen")
    p_tr.add_argument("pdf", help="Pfad zum englischen PDF")
    p_tr.add_argument("--tool", choices=["offline", "api"], default=None, help="Werkzeug (Standard: aus Einstellungen)")
    p_tr.add_argument("--online", action="store_true", help="Bestätigt den bewussten Online-Betrieb (Mistral-API)")
    p_tr.add_argument("--api-key", default=None, help="Mistral-API-Schlüssel (sonst aus settings.json)")
    p_tr.add_argument("--api-model", default=None, help="API-Modellname (Standard: mistral-small-latest)")
    p_tr.add_argument("--model", default=None, help="Pfad zum lokalen GGUF-Modell")
    p_tr.add_argument("--out", dest="output_dir", default=None, help="Zielordner für die EPUB-Datei")
    p_tr.add_argument("--glossar", default=None, help="Pfad zur Glossar-Textdatei (Begriff = Übersetzung)")
    p_tr.add_argument("--chunk-size", type=int, default=None, help="Wörter pro Abschnitt (Standard: 1500)")
    p_tr.add_argument("--temperature", type=float, default=None, help="Temperatur (Standard: 0,3)")
    p_tr.add_argument("--no-resume", action="store_true", help="Keinen vorhandenen Zwischenspeicher verwenden")
    p_tr.add_argument("--no-cover", action="store_true", help="Kein Deckbild aus der ersten PDF-Seite übernehmen")
    p_tr.set_defaults(func=_cmd_uebersetzen)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
