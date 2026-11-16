"""Hauptfenster der Anwendung (PySide6/Qt 6).

- PDF-Import per Dateidialog und Drag & Drop
- Fortschrittsbalken, aktuelle Seite, Abschnitte, geschätzte Restdauer, Live-Textprobe
- Abbrechen-Knopf (wirkt sofort, GUI bleibt bedienbar – Übersetzung läuft im Hintergrund-Thread)
- Fortsetzen nach Unterbrechung (JSON-Zwischenspeicher)
- Einstellungen (persistiert in settings.json) inkl. Modellverwaltung
- Abschluss-Zusammenfassung mit Knopf „Ablageordner öffnen“
- Alle Fehlermeldungen auf Deutsch, nie nackte Stapelverfolgungen
"""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QProgressDialog,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from . import model_manager, pdf_reader, report as report_mod
from .cache import TranslationCache
from .pipeline import CancelledError, PipelineListener, TranslationPipeline
from .settings import LEGACY_HF_FILENAMES, MODEL_PRESETS, Settings, model_preset_index, save_settings
from .translator_base import load_glossary
from .wizard import DownloadWorker, FirstStartWizard


def fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"ca. {h} h {m} min"
    if m:
        return f"ca. {m} min {s} s"
    return f"ca. {s} s"


class _Worker(QThread):
    """Führt Extraktion + Übersetzung im Hintergrund aus."""

    log = Signal(str)
    status = Signal(str)
    progress = Signal(int, int)
    page_info = Signal(int)
    eta = Signal(float)
    preview = Signal(str)
    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, pdf_path: Path, settings: Settings, cache: TranslationCache, output_path: Path | None, parent=None):
        super().__init__(parent)
        self.pdf_path = Path(pdf_path)
        self.settings = settings
        self.cache = cache
        self.output_path = output_path
        self.cancel_event = threading.Event()
        self._translator = None

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        try:
            def _extract_progress(page_nr: int, page_total: int, modus: str) -> None:
                if modus == "OCR":
                    self.log.emit(f"Seite {page_nr}/{page_total}: OCR (gescannte Seite) …")

            ocr_backend = self.settings.effective_ocr_backend(self.settings.tool, self.settings.online_enabled)
            if self.settings.ocr_backend == "mistral" and ocr_backend != "mistral":
                self.log.emit("Hinweis: Mistral OCR ist nur im Online-Betrieb verfügbar – lokales OCR wird verwendet.")
            book = pdf_reader.extract_book(
                self.pdf_path,
                ocr=self.settings.ocr_enabled,
                progress_cb=_extract_progress,
                ocr_backend=ocr_backend,
                api_key=self.settings.api_key,
            )
            self.log.emit(
                f"PDF geladen: {book.title} – {book.page_count} Seiten, {book.word_count} Wörter, "
                f"{len(book.chapters)} Kapitel erkannt."
            )
            if self.settings.tool == "api":
                if not self.settings.online_enabled:
                    self.failed.emit(
                        "Der Online-Betrieb ist ausgeschaltet. Bitte in den Einstellungen bewusst "
                        "einschalten (dann wird der Buchtext an Mistral übertragen) oder den Offline-Modus wählen."
                    )
                    return
                from .translator_api import ApiError, ApiTranslator

                try:
                    self._translator = ApiTranslator(
                        self.settings.api_key,
                        self.settings.api_model,
                        self.settings.api_endpoint,
                        self.settings.temperature,
                    )
                except ApiError as exc:
                    self.failed.emit(str(exc))
                    return
            else:
                from .translator_local import LocalTranslator

                try:
                    self._translator = LocalTranslator(self.settings.resolved_model_path())
                except FileNotFoundError as exc:
                    self.failed.emit(f"{exc}\nTipp: Modell laden über Einstellungen → „Modell laden“.")
                    return
                if self._translator.gpu_warning:
                    self.log.emit(f"Warnung: {self._translator.gpu_warning}")

            listener = _GuiListener(self)
            pipeline = TranslationPipeline(
                book=book,
                translator=self._translator,
                settings=self.settings,
                cache=self.cache,
                listener=listener,
                cancel_event=self.cancel_event,
                glossary=load_glossary(self.settings.glossary_path),
                output_path=self.output_path,
                cover_png=pdf_reader.extract_cover_png(self.pdf_path),
            )
            result = pipeline.run()
            self.finished.emit(result)
        except CancelledError:
            self.cancelled.emit()
        except pdf_reader.PdfError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(f"Unerwarteter Fehler: {exc}")
        finally:
            if self._translator is not None and hasattr(self._translator, "close"):
                try:
                    self._translator.close()
                except Exception:
                    pass


class _UpdateWorker(QObject):
    """Lädt den Update-Installer im Hintergrund (mit Fortschritt/Abbruch)."""

    progress = Signal(int, int, float)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, release: dict, dest_dir: Path):
        super().__init__()
        self.release = release
        self.dest_dir = dest_dir
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        from . import updater

        try:
            dest = updater.download_installer(
                self.release["asset_url"],
                self.dest_dir,
                asset_name=self.release["asset_name"],
                progress_cb=lambda d, t, s: self.progress.emit(d, t, s),
                cancel_event=self.cancel_event,
            )
        except updater.UpdateCancelled:
            self.failed.emit("abgebrochen")
            return
        except updater.UpdateError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:
            self.failed.emit(f"Unerwarteter Fehler: {exc}")
            return
        self.finished.emit(str(dest))


class _GuiListener(PipelineListener):
    def __init__(self, worker: _Worker):
        self.worker = worker

    def on_start(self, total_chunks: int, resumed: bool) -> None:
        self.worker.status.emit(
            f"{total_chunks} Abschnitte zu übersetzen" + (" (Fortsetzung aus Zwischenspeicher)" if resumed else "")
        )

    def on_chunk_start(self, chunk, done: int, total: int) -> None:
        self.worker.status.emit(f"Abschnitt {done + 1} von {total} (ab Seite {chunk.page}) …")
        self.worker.page_info.emit(chunk.page)
        self.worker.preview.emit("\n")

    def on_token(self, text: str) -> None:
        self.worker.preview.emit(text)

    def on_chunk_done(self, chunk, translation, done: int, total: int, problem) -> None:
        self.worker.progress.emit(done, total)
        if problem:
            self.worker.log.emit(f"Abschnitt {chunk.index + 1} fehlgeschlagen ({problem}) – Notiz im EPUB.")

    def on_progress(self, info) -> None:
        self.worker.progress.emit(info.done, info.total)
        self.worker.eta.emit(info.eta_seconds)
        self.worker.status.emit(
            f"Abschnitt {info.done}/{info.total} – Seite {info.page} – "
            f"verstrichen {fmt_duration(info.elapsed_seconds)}"
        )

    def on_log(self, message: str) -> None:
        self.worker.log.emit(message)


class SettingsDialog(QDialog):
    """Einstellungen – persistiert in settings.json im Benutzerprofil."""

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Einstellungen")
        self.resize(620, 560)

        form = QFormLayout()

        self.cmb_tool = QComboBox()
        self.cmb_tool.addItem("Offline (lokal, empfohlen)", "offline")
        self.cmb_tool.addItem("Mistral-API (Online-Notnagel)", "api")
        self.cmb_tool.setCurrentIndex(0 if settings.tool == "offline" else 1)
        form.addRow("Werkzeug:", self.cmb_tool)

        self.chk_online = QCheckBox("Online-Betrieb bewusst einschalten")
        self.chk_online.setChecked(settings.online_enabled)
        self.lbl_online_warning = QLabel(
            "ACHTUNG: Eingeschaltet wird der Buchtext an Mistral (api.mistral.ai) übertragen. "
            "Ohne Häkchen verlässt kein Buchinhalt das Gerät."
        )
        self.lbl_online_warning.setWordWrap(True)
        form.addRow("Online-Betrieb:", self.chk_online)
        form.addRow("", self.lbl_online_warning)

        self.txt_api_key = QLineEdit(settings.api_key)
        self.txt_api_key.setEchoMode(QLineEdit.Password)
        form.addRow("API-Schlüssel:", self.txt_api_key)
        self.txt_api_model = QLineEdit(settings.api_model)
        form.addRow("API-Modell:", self.txt_api_model)

        self.spin_temp = QDoubleSpinBox()
        self.spin_temp.setRange(0.0, 1.0)
        self.spin_temp.setSingleStep(0.05)
        self.spin_temp.setValue(settings.temperature)
        form.addRow("Temperatur:", self.spin_temp)

        self.spin_chunk = QSpinBox()
        self.spin_chunk.setRange(200, 5000)
        self.spin_chunk.setSingleStep(100)
        self.spin_chunk.setValue(settings.chunk_size)
        form.addRow("Wörter pro Abschnitt:", self.spin_chunk)

        self.chk_ocr = QCheckBox("Gescannte PDF-Seiten per OCR erkennen (langsamer)")
        self.chk_ocr.setChecked(settings.ocr_enabled)
        form.addRow("OCR:", self.chk_ocr)

        self.cmb_ocr_backend = QComboBox()
        self.cmb_ocr_backend.addItem("Lokal (RapidOCR, ohne Datenversand)", "local")
        self.cmb_ocr_backend.addItem("Mistral OCR – nur im Online-Betrieb, Seitenbilder gehen an Mistral", "mistral")
        self.cmb_ocr_backend.setCurrentIndex(1 if settings.ocr_backend == "mistral" else 0)
        form.addRow("OCR-Backend:", self.cmb_ocr_backend)

        glossar_row = QHBoxLayout()
        self.txt_glossar = QLineEdit(settings.glossary_path)
        btn_glossar = QPushButton("…")
        btn_glossar.clicked.connect(self._pick_glossar)
        glossar_row.addWidget(self.txt_glossar)
        glossar_row.addWidget(btn_glossar)
        form.addRow("Glossar-Datei:", glossar_row)

        out_row = QHBoxLayout()
        self.txt_output = QLineEdit(str(settings.resolved_output_dir()))
        btn_out = QPushButton("…")
        btn_out.clicked.connect(self._pick_output)
        out_row.addWidget(self.txt_output)
        out_row.addWidget(btn_out)
        form.addRow("Zielordner (EPUB):", out_row)

        model_row = QHBoxLayout()
        self.txt_model = QLineEdit(str(settings.resolved_model_path()))
        btn_model_file = QPushButton("…")
        btn_model_file.clicked.connect(self._pick_model_file)
        model_row.addWidget(self.txt_model)
        model_row.addWidget(btn_model_file)
        form.addRow("Offline-Modell:", model_row)

        self.cmb_model = QComboBox()
        for p in MODEL_PRESETS:
            self.cmb_model.addItem(p["label"], p["id"])
        idx = model_preset_index(settings.hf_repo, settings.hf_filename)
        self.cmb_model.setCurrentIndex(idx if idx >= 0 else 0)
        form.addRow("Modell-Download:", self.cmb_model)
        self.lbl_model_hint = QLabel("")
        self.lbl_model_hint.setWordWrap(True)
        form.addRow("", self.lbl_model_hint)
        self._update_model_hint()

        self.lbl_model_usage = QLabel("")
        self.lbl_model_usage.setWordWrap(True)
        form.addRow("Speicher:", self.lbl_model_usage)

        model_btn_row = QHBoxLayout()
        self.btn_model_download = QPushButton("Modell laden")
        self.btn_model_delete = QPushButton("Modell löschen")
        self.btn_model_download.clicked.connect(self._download_model)
        self.btn_model_delete.clicked.connect(self._delete_model)
        model_btn_row.addWidget(self.btn_model_download)
        model_btn_row.addWidget(self.btn_model_delete)
        form.addRow("", model_btn_row)

        self.btn_wizard = QPushButton("Erststart-Assistenten erneut öffnen")
        self.btn_wizard.clicked.connect(self._rerun_wizard)
        form.addRow("", self.btn_wizard)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self._refresh_usage()

    def _pick_glossar(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Glossar-Datei wählen", "", "Textdateien (*.txt);;Alle Dateien (*)")
        if path:
            self.txt_glossar.setText(path)

    def _pick_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Zielordner wählen", self.txt_output.text())
        if path:
            self.txt_output.setText(path)

    def _pick_model_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "GGUF-Modell wählen", "", "GGUF-Modelle (*.gguf);;Alle Dateien (*)")
        if path:
            self.txt_model.setText(path)

    def _refresh_usage(self) -> None:
        model_path = Path(self.txt_model.text())
        usage = model_manager.model_disk_usage(model_path)
        parent = model_path.parent if model_path.parent.exists() else Path.home()
        free = model_manager.free_space_bytes(parent)
        state = "vorhanden" if model_manager.is_model_present(model_path) else "nicht vorhanden"
        self.lbl_model_usage.setText(
            f"Modell {state}: {model_path}\nBelegt: {model_manager.format_bytes(usage)} – "
            f"frei auf dem Laufwerk: {model_manager.format_bytes(free)}"
        )

    def _update_model_hint(self) -> None:
        current = self.settings.resolved_model_path().name
        if current in LEGACY_HF_FILENAMES:
            self.lbl_model_hint.setText(
                "Hinweis: Es ist ein älteres Modell geladen. Für deutlich bessere Übersetzungen "
                "oben ein aktuelles Modell wählen und „Modell laden“ klicken."
            )
        else:
            self.lbl_model_hint.setText("")

    def _download_model(self) -> None:
        preset = MODEL_PRESETS[self.cmb_model.currentIndex()]
        s = Settings(**self.settings.to_dict())
        s.hf_repo = preset["repo"]
        s.hf_filename = preset["filename"]
        s.model_path = self.txt_model.text().strip()
        dest = s.resolved_model_path()
        if model_manager.is_model_present(dest):
            QMessageBox.information(self, "Modell laden", f"Das gewählte Modell ist bereits vorhanden:\n{dest}")
            return
        progress = QProgressDialog(f"Modell wird geladen: {preset['filename']}", "Abbrechen", 0, 0, self)
        progress.setWindowTitle("Modell-Download")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        worker = DownloadWorker(s)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        def _on_progress(d, t, sp):
            if t > 0:
                progress.setMaximum(t)
            progress.setValue(d)
            progress.setLabelText(
                f"{model_manager.format_bytes(d)} von {model_manager.format_bytes(t)} ({model_manager.format_bytes(sp)}/s)"
            )

        def _stop():
            progress.reset()
            progress.hide()
            thread.quit()
            thread.wait(3000)
            self._refresh_usage()

        worker.progress.connect(_on_progress)
        worker.finished.connect(lambda p: (_stop(), QMessageBox.information(self, "Modell geladen", f"Fertig:\n{p}")))
        worker.failed.connect(lambda m: (_stop(), None if m == "abgebrochen" else QMessageBox.warning(self, "Download fehlgeschlagen", m)))
        worker.cancelled.connect(lambda: _stop())
        progress.canceled.connect(worker.cancel)
        progress.show()
        thread.start()

    def _delete_model(self) -> None:
        model_path = Path(self.txt_model.text())
        if not model_manager.is_model_present(model_path):
            QMessageBox.information(self, "Modell löschen", "Es ist kein Modell an diesem Pfad vorhanden.")
            return
        answer = QMessageBox.question(
            self, "Modell löschen",
            f"Soll das Modell wirklich gelöscht werden?\n{model_path}\n"
            "(Es kann später jederzeit erneut heruntergeladen werden.)",
        )
        if answer == QMessageBox.Yes:
            freed = model_manager.delete_model(model_path)
            QMessageBox.information(self, "Modell gelöscht", f"Freigegeben: {model_manager.format_bytes(freed)}")
            self._refresh_usage()

    def _rerun_wizard(self) -> None:
        wiz = FirstStartWizard(self.settings, self)
        wiz.exec()

    def _accept(self) -> None:
        s = self.settings
        s.tool = self.cmb_tool.currentData()
        s.online_enabled = self.chk_online.isChecked()
        s.api_key = self.txt_api_key.text().strip()
        s.api_model = self.txt_api_model.text().strip() or "mistral-small-latest"
        s.temperature = self.spin_temp.value()
        s.chunk_size = self.spin_chunk.value()
        s.ocr_enabled = self.chk_ocr.isChecked()
        s.ocr_backend = self.cmb_ocr_backend.currentData()
        preset = MODEL_PRESETS[self.cmb_model.currentIndex()]
        s.hf_repo = preset["repo"]
        s.hf_filename = preset["filename"]
        s.glossary_path = self.txt_glossar.text().strip()
        s.output_dir = self.txt_output.text().strip()
        s.model_path = self.txt_model.text().strip()
        save_settings(s)
        self.accept()


class SummaryDialog(QDialog):
    """Zusammenfassung nach Abschluss inkl. Verbrauch (API) und Ablageordner-Knopf."""

    def __init__(self, result, tool: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Übersetzung abgeschlossen")
        self.resize(520, 320)
        layout = QVBoxLayout(self)
        text = QLabel()
        lines = [
            f"Seiten: {result.pages}",
            f"Wörter: {result.words}",
            f"Abschnitte: {result.chunks_done} übersetzt, {result.chunks_failed} fehlgeschlagen (von {result.chunks_total})",
            f"Dauer: {fmt_duration(result.duration_seconds)}",
        ]
        if tool == "api":
            lines.append(f"An Mistral gesendete Zeichen: {result.chars_sent} (für die Kostenschätzung)")
        lines.append(f"Ausgabedatei: {result.output_path}")
        text.setText("\n".join(lines))
        text.setWordWrap(True)
        layout.addWidget(text)
        row = QHBoxLayout()
        btn_open = QPushButton("Ablageordner öffnen")
        btn_open.clicked.connect(self._open_folder)
        btn_close = QPushButton("Schließen")
        btn_close.clicked.connect(self.accept)
        row.addWidget(btn_open)
        row.addWidget(btn_close)
        layout.addLayout(row)
        self._result = result

    def _open_folder(self) -> None:
        folder = str(Path(self._result.output_path).parent)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Gideon's Übersetzer")
        self.resize(760, 640)
        self.setAcceptDrops(True)
        self._worker: _Worker | None = None

        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # PDF-Auswahl
        pdf_row = QHBoxLayout()
        self.txt_pdf = QLineEdit()
        self.txt_pdf.setPlaceholderText("Englisches PDF hierher ziehen oder wählen …")
        self.txt_pdf.setReadOnly(True)
        btn_browse = QPushButton("PDF wählen …")
        btn_browse.clicked.connect(self._browse_pdf)
        pdf_row.addWidget(self.txt_pdf)
        pdf_row.addWidget(btn_browse)
        layout.addLayout(pdf_row)

        # Werkzeug + Einstellungen
        tool_row = QHBoxLayout()
        self.lbl_tool = QLabel()
        btn_settings = QPushButton("Einstellungen …")
        btn_settings.clicked.connect(self._open_settings)
        btn_report = QPushButton("Report erstellen …")
        btn_report.setToolTip("Diagnose-Report als Markdown-Datei speichern (kein API-Schlüssel, keine Buchinhalte)")
        btn_report.clicked.connect(self._create_report)
        btn_update = QPushButton("Update …")
        btn_update.setToolTip("Manuell nach neuer Version auf GitHub suchen (kontaktiert api.github.com)")
        btn_update.clicked.connect(self._check_update)
        tool_row.addWidget(self.lbl_tool)
        tool_row.addStretch(1)
        tool_row.addWidget(btn_update)
        tool_row.addWidget(btn_report)
        tool_row.addWidget(btn_settings)
        layout.addLayout(tool_row)

        glossar_row = QHBoxLayout()
        glossar_row.addWidget(QLabel("Glossar:"))
        self.txt_glossar = QLineEdit(settings.glossary_path)
        self.txt_glossar.setPlaceholderText("optional: Textdatei mit „Begriff = Übersetzung“-Zeilen")
        btn_glossar = QPushButton("…")
        btn_glossar.clicked.connect(lambda: self._pick_file(self.txt_glossar, "Glossar wählen", "Textdateien (*.txt);;Alle (*)"))
        glossar_row.addWidget(self.txt_glossar)
        glossar_row.addWidget(btn_glossar)
        layout.addLayout(glossar_row)

        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Zielordner:"))
        self.txt_output = QLineEdit(str(settings.resolved_output_dir()))
        btn_out = QPushButton("…")
        btn_out.clicked.connect(lambda: self._pick_dir(self.txt_output))
        out_row.addWidget(self.txt_output)
        out_row.addWidget(btn_out)
        layout.addLayout(out_row)

        # Start/Abbrechen
        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("Übersetzen starten")
        self.btn_start.clicked.connect(self._start)
        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel)
        btn_row.addWidget(self.btn_start)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # Fortschritt
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        self.lbl_status = QLabel("Bereit.")
        layout.addWidget(self.lbl_status)
        self.lbl_eta = QLabel("")
        layout.addWidget(self.lbl_eta)

        layout.addWidget(QLabel("Live-Textprobe (gerade übersetzter Abschnitt):"))
        self.txt_preview = QPlainTextEdit()
        self.txt_preview.setReadOnly(True)
        layout.addWidget(self.txt_preview)

        layout.addWidget(QLabel("Protokoll:"))
        self.txt_log = QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setMaximumBlockCount(500)
        layout.addWidget(self.txt_log)

        self._refresh_tool_label()

    # --- Anzeige ---

    def _on_worker_log(self, message: str) -> None:
        report_mod.add_log_line(message)
        self.txt_log.appendPlainText(message)

    def _create_report(self) -> None:
        try:
            path = report_mod.write_report(self.settings)
        except OSError as exc:
            QMessageBox.warning(self, "Report", f"Report konnte nicht gespeichert werden: {exc}")
            return
        QMessageBox.information(
            self,
            "Report erstellt",
            f"Diagnose-Report gespeichert unter:\n{path}\n\n"
            "Zum Fehlerfinden/Qualität verbessern einfach diese Markdown-Datei weitergeben "
            "(enthält keinen API-Schlüssel und keine Buchinhalte).",
        )

    def _check_update(self) -> None:
        from . import __version__, updater

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            release = updater.check_for_update()
        except updater.UpdateError as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Update", f"Update-Prüfung fehlgeschlagen: {exc}")
            return
        QApplication.restoreOverrideCursor()
        if release is None:
            QMessageBox.information(self, "Update", f"Version {__version__} ist aktuell – kein Update verfügbar.")
            return
        answer = QMessageBox.question(
            self,
            "Update verfügbar",
            f"Neue Version v{release['version']} ist verfügbar (installiert: v{__version__}).\n\n"
            f"Jetzt {release['asset_name']} herunterladen und installieren?\n"
            "Hinweis: Dafür wurde api.github.com kontaktiert; der Installer wird von github.com geladen.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._download_update(release)

    def _download_update(self, release: dict) -> None:
        from . import updater

        self._update_progress = QProgressDialog(f"Update v{release['version']} wird geladen …", "Abbrechen", 0, 0, self)
        self._update_progress.setWindowTitle("Update")
        self._update_progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._update_thread = QThread(self)
        self._update_worker = _UpdateWorker(release, updater.default_download_dir())
        self._update_worker.moveToThread(self._update_thread)
        self._update_thread.started.connect(self._update_worker.run)
        self._update_worker.progress.connect(self._on_update_progress)
        self._update_worker.finished.connect(self._on_update_finished)
        self._update_worker.failed.connect(self._on_update_failed)
        self._update_progress.canceled.connect(self._update_worker.cancel)
        self._update_progress.setMinimumDuration(0)
        self._update_progress.show()
        self._update_thread.start()

    def _on_update_progress(self, done: int, total: int, speed: float) -> None:
        if total > 0:
            self._update_progress.setMaximum(total)
            self._update_progress.setValue(done)
        self._update_progress.setLabelText(f"{done / 1e6:.1f} / {total / 1e6:.1f} MB ({speed / 1e6:.1f} MB/s)")

    def _on_update_finished(self, path: str) -> None:
        self._update_progress.reset()
        self._update_progress.hide()
        self._update_thread.quit()
        self._update_thread.wait()
        from . import updater

        answer = QMessageBox.question(
            self,
            "Update heruntergeladen",
            f"Installer gespeichert: {path}\n\nJetzt installieren? Die App wird dabei beendet und aktualisiert.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            updater.run_installer(Path(path))
            QApplication.quit()

    def _on_update_failed(self, message: str) -> None:
        self._update_progress.reset()
        self._update_progress.hide()
        self._update_thread.quit()
        self._update_thread.wait()
        if message != "abgebrochen":
            QMessageBox.warning(self, "Update", f"Update-Download fehlgeschlagen: {message}")

    def _refresh_tool_label(self) -> None:
        if self.settings.tool == "api":
            state = "EIN" if self.settings.online_enabled else "AUS"
            self.lbl_tool.setText(
                f"Werkzeug: Mistral-API (Online-Betrieb: {state}) – "
                + ("sendet Buchtext an Mistral!" if self.settings.online_enabled else "nicht aktiv")
            )
        else:
            self.lbl_tool.setText("Werkzeug: OFFLINE (lokal, empfohlen) – kein Buchinhalt verlässt das Gerät")

    # --- Datei-Dialoge / Drag & Drop ---

    def _browse_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Englisches PDF wählen", "", "PDF-Dateien (*.pdf);;Alle Dateien (*)")
        if path:
            self.txt_pdf.setText(path)

    def _pick_file(self, edit: QLineEdit, title: str, filt: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, title, "", filt)
        if path:
            edit.setText(path)

    def _pick_dir(self, edit: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, "Zielordner wählen", edit.text())
        if path:
            edit.setText(path)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls() and any(u.toLocalFile().lower().endswith(".pdf") for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        for url in event.mimeData().urls():
            local = url.toLocalFile()
            if local.lower().endswith(".pdf"):
                self.txt_pdf.setText(local)
                event.acceptProposedAction()
                return

    # --- Einstellungen ---

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec() == QDialog.Accepted:
            self.txt_glossar.setText(self.settings.glossary_path)
            self.txt_output.setText(str(self.settings.resolved_output_dir()))
            self._refresh_tool_label()

    # --- Übersetzung starten / abbrechen ---

    def _start(self) -> None:
        pdf_path = Path(self.txt_pdf.text().strip())
        if not pdf_path.is_file():
            QMessageBox.warning(self, "Kein PDF gewählt", "Bitte zuerst ein englisches PDF auswählen oder hierher ziehen.")
            return
        if self.settings.tool == "offline" and not model_manager.is_model_present(self.settings.resolved_model_path()):
            answer = QMessageBox.question(
                self, "Modell fehlt",
                "Das Offline-Modell ist noch nicht geladen. Jetzt laden?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
            )
            if answer == QMessageBox.Yes:
                self._open_settings()
            return
        if self.settings.tool == "api" and not self.settings.online_enabled:
            QMessageBox.information(
                self, "Online-Betrieb ausgeschaltet",
                "Der Online-Betrieb ist ausgeschaltet. Bitte in den Einstellungen bewusst einschalten "
                "(der Buchtext wird dann an Mistral übertragen) oder den Offline-Modus verwenden.",
            )
            return

        self.settings.glossary_path = self.txt_glossar.text().strip()
        self.settings.output_dir = self.txt_output.text().strip()
        save_settings(self.settings)

        cache = TranslationCache.load(pdf_path)
        if cache is not None:
            answer = QMessageBox.question(
                self, "Übersetzung fortsetzen?",
                f"Für „{pdf_path.name}“ existiert ein Zwischenspeicher mit {cache.done_count} bereits "
                f"übersetzten Abschnitten.\n\nSoll die Übersetzung fortgesetzt werden?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
            )
            if answer != QMessageBox.Yes:
                cache = TranslationCache(pdf_path, TranslationCache.cache_file_for(pdf_path), tool=self.settings.tool)
        else:
            cache = TranslationCache(pdf_path, TranslationCache.cache_file_for(pdf_path), tool=self.settings.tool)

        output_path = None
        self.txt_preview.clear()
        self.txt_log.clear()
        self.progress.setValue(0)
        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.lbl_status.setText("PDF wird gelesen …")

        self._worker = _Worker(pdf_path, self.settings, cache, output_path, self)
        w = self._worker
        w.log.connect(self._on_worker_log)
        w.status.connect(self.lbl_status.setText)
        w.progress.connect(self._on_progress)
        w.eta.connect(lambda e: self.lbl_eta.setText(f"Geschätzte Restdauer: {fmt_duration(e)}" if e else ""))
        w.preview.connect(self._append_preview)
        w.finished.connect(self._on_finished)
        w.failed.connect(self._on_failed)
        w.cancelled.connect(self._on_cancelled)
        w.start()

    def _on_progress(self, done: int, total: int) -> None:
        self.progress.setMaximum(total)
        self.progress.setValue(done)

    def _append_preview(self, text: str) -> None:
        self.txt_preview.moveCursor(QTextCursor.End)
        self.txt_preview.insertPlainText(text)
        plain = self.txt_preview.toPlainText()
        if len(plain) > 4000:
            self.txt_preview.setPlainText(plain[-4000:])

    def _cancel(self) -> None:
        if self._worker is not None:
            self.btn_cancel.setEnabled(False)
            self.lbl_status.setText("Abbruch wird wirksam …")
            self._worker.cancel()

    def _on_finished(self, result) -> None:
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.lbl_eta.setText("")
        self.lbl_status.setText("Fertig.")
        self.txt_log.appendPlainText("EPUB geschrieben: " + str(result.output_path))
        dlg = SummaryDialog(result, self.settings.tool, self)
        dlg.exec()

    def _on_failed(self, message: str) -> None:
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.lbl_eta.setText("")
        self.lbl_status.setText("Fehler.")
        self.txt_log.appendPlainText("Fehler: " + message)
        QMessageBox.critical(self, "Fehler", message)

    def _on_cancelled(self) -> None:
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.lbl_eta.setText("")
        self.lbl_status.setText("Abgebrochen.")
        self.txt_log.appendPlainText(
            "Übersetzung abgebrochen. Zwischenspeicher gesichert – beim erneuten Öffnen desselben PDFs "
            "kann fortgesetzt werden."
        )
        QMessageBox.information(
            self, "Abgebrochen",
            "Die Übersetzung wurde abgebrochen. Die bisher übersetzten Abschnitte sind gesichert; "
            "beim erneuten Start desselben PDFs wird angeboten, fortzusetzen.",
        )
