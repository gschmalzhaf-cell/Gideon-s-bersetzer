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
    """Warteschlange: alle übergebenen Dokumente (PDF/EPUB/DOCX) nacheinander abarbeiten."""
    from . import document_reader

    settings = settings_mod.load_settings()
    if args.output_dir:
        settings.output_dir = args.output_dir
    if args.glossar:
        settings.glossary_path = args.glossar
    if args.chunk_size:
        settings.chunk_size = args.chunk_size
    if args.temperature is not None:
        settings.temperature = args.temperature

    ocr = not args.no_ocr and settings.ocr_enabled
    if not ocr:
        print("Hinweis: OCR ist ausgeschaltet – reine Scan-PDFs werden abgelehnt.")

    tool = args.tool or settings.tool
    online = settings.online_enabled or args.online
    ocr_backend = args.ocr_backend or settings.ocr_backend
    if ocr_backend == "mistral" and not (tool == "api" and online):
        print("Hinweis: Mistral OCR ist nur im Online-Betrieb (Mistral-API, bewusst eingeschaltet) verfügbar – "
              "lokales OCR wird verwendet.")
        ocr_backend = "local"

    # Translator wird erst nach dem ersten erfolgreich gelesenen Dokument geladen und
    # dann für die ganze Warteschlange wiederverwendet (sonst würde das 4-7-GB-Modell
    # pro Dokument neu geladen). Dokument-Fehler haben Vorrang vor Modell-Fehlern.
    translator = None
    tool = args.tool or settings.tool

    def _extract_progress(page_nr: int, page_total: int, modus: str) -> None:
        if modus == "OCR":
            print(f"  Seite {page_nr}/{page_total}: OCR (gescannte Seite) …", flush=True)

    documents = [Path(p) for p in args.pdf]
    failures = 0
    cancelled = False
    try:
        for i, doc_path in enumerate(documents, start=1):
            print(f"\n=== Dokument {i}/{len(documents)}: {doc_path.name} ===", flush=True)
            try:
                book = document_reader.read_book(
                    doc_path,
                    ocr=ocr,
                    progress_cb=_extract_progress,
                    ocr_backend=ocr_backend,
                    api_key=args.api_key or settings.api_key,
                )
            except pdf_reader.PdfError as exc:
                print(f"Fehler: {exc}")
                failures += 1
                continue
            if doc_path.suffix.lower() == ".pdf":
                print(f"PDF geladen: {book.title} – {book.page_count} Seiten, {book.word_count} Wörter, "
                      f"{len(book.chapters)} Kapitel erkannt.")
            else:
                print(f"Dokument geladen: {book.title} – {book.word_count} Wörter, "
                      f"{len(book.chapters)} Kapitel erkannt.")

            if translator is None:
                built = _build_translator(args, settings)
                if built is None:
                    return 1
                translator, tool = built

            cache = TranslationCache.load(doc_path)
            if cache is not None and not args.no_resume:
                answer = input(f"Es existiert ein Zwischenspeicher für {doc_path.name}. Übersetzung fortsetzen? [J/n] ")
                if answer.strip().lower() not in ("", "j", "ja", "y", "yes"):
                    cache = None
            if cache is None:
                cache = TranslationCache(doc_path, TranslationCache.cache_file_for(doc_path), tool=tool)

            cover = None
            if not args.no_cover and doc_path.suffix.lower() == ".pdf":
                cover = pdf_reader.extract_cover_png(doc_path)

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
                print("\nÜbersetzung abgebrochen. Zwischenspeicher wurde gesichert – Fortsetzen später möglich.")
                cancelled = True
                break
            print(f"=== Zusammenfassung {doc_path.name} ===")
            print(f"Wörter: {result.words}")
            print(f"Abschnitte: {result.chunks_done} übersetzt, {result.chunks_failed} fehlgeschlagen (von {result.chunks_total})")
            print(f"Dauer: {_fmt_duration(result.duration_seconds)}")
            if tool == "api":
                print(f"An Mistral gesendete Zeichen: {result.chars_sent}")
            print(f"Ausgabedatei: {result.output_path}")
    finally:
        if translator is not None and hasattr(translator, "close"):
            translator.close()

    if cancelled:
        return 130
    print(f"\n=== Warteschlange fertig: {len(documents) - failures}/{len(documents)} erfolgreich ===")
    return 0 if failures == 0 else 1


def _cmd_update(args) -> int:
    from . import __version__, updater

    try:
        rel = updater.latest_release()
    except updater.UpdateError as exc:
        print(f"Fehler: {exc}")
        return 1
    print(f"Installierte Version: {__version__} – neueste GitHub-Release: v{rel['version']} ({rel['asset_name']})")
    if not updater.is_newer(rel["version"], __version__):
        print("Kein Update verfügbar – die installierte Version ist aktuell.")
        return 0
    if args.check:
        print("Update verfügbar (nur Prüfung mit --check).")
        return 0
    dest_dir = updater.default_download_dir()
    print(f"Lade {rel['asset_name']} nach {dest_dir} …")
    try:
        path = updater.download_installer(
            rel["asset_url"],
            dest_dir,
            asset_name=rel["asset_name"],
            progress_cb=lambda d, t, s: print(f"\r  {d}/{t} Bytes", end="", flush=True),
        )
    except updater.UpdateError as exc:
        print(f"\nFehler: {exc}")
        return 1
    except updater.UpdateCancelled:
        print("\nDownload abgebrochen (Fortsetzen beim nächsten Aufruf möglich).")
        return 130
    print(f"\nInstaller gespeichert: {path}")
    updater.run_installer(path)
    print("Installer gestartet – die App wird dabei auf v" + rel["version"] + " aktualisiert.")
    return 0


def _cmd_report(args) -> int:
    from . import report

    settings = settings_mod.load_settings()
    out = Path(args.report_out) if args.report_out else None
    path = report.write_report(settings, out)
    print(f"Report gespeichert: {path}\n")
    print(report.build_report(settings))
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
    p_tr.add_argument("pdf", nargs="+", metavar="dokument", help="ein oder mehrere englische Dokumente (PDF/EPUB/DOCX) – Warteschlange, nacheinander abgearbeitet")
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
    p_tr.add_argument("--no-ocr", action="store_true", help="OCR ausschalten – reine Scan-PDFs werden abgelehnt")
    p_tr.add_argument("--ocr-backend", choices=["local", "mistral"], default=None,
                      help="OCR-Backend für Scans (Standard: aus Einstellungen). 'mistral' nur im Online-Betrieb – "
                           "Seitenbilder werden dann an Mistral gesendet")
    p_tr.set_defaults(func=_cmd_uebersetzen)

    p_rep = sub.add_parser("report", help="Diagnose-Report (Markdown + JSON-Anhang) erstellen")
    p_rep.add_argument("--out", dest="report_out", default=None,
                       help="Zieldatei (Standard: Zielordner mit Zeitstempel); der Report wird auch ausgegeben")
    p_rep.set_defaults(func=_cmd_report)

    p_up = sub.add_parser("update", help="Nach neuerer Version auf GitHub suchen und Installer laden/installieren "
                                         "(kontaktiert api.github.com bzw. github.com – nur auf ausdrücklichen Aufruf)")
    p_up.add_argument("--check", action="store_true", help="Nur prüfen und melden, nichts herunterladen")
    p_up.set_defaults(func=_cmd_update)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
