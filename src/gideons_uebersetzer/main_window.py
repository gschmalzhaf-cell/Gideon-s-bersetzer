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
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QProgressDialog,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import intelligence, model_manager, pdf_reader, report as report_mod
from . import theme as theme_mod
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
    """Führt Extraktion + Übersetzung der Warteschlange im Hintergrund aus (ein Translator für alle Dokumente)."""

    log = Signal(str)
    status = Signal(str)
    progress = Signal(int, int)
    page_info = Signal(int)
    eta = Signal(float)
    preview = Signal(str)
    finished = Signal(object)  # list[dict]: {path, ok, result, error}
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, paths, settings: Settings, parent=None, resume: bool = True):
        super().__init__(parent)
        self.paths = [Path(p) for p in paths]
        self.settings = settings
        self.resume = resume
        self.cancel_event = threading.Event()
        self._translator = None

    def cancel(self) -> None:
        self.cancel_event.set()

    def _make_translator(self):
        if self.settings.tool == "api":
            if not self.settings.online_enabled:
                raise RuntimeError(
                    "Der Online-Betrieb ist ausgeschaltet. Bitte in den Einstellungen bewusst einschalten "
                    "(dann wird der Buchtext an Mistral übertragen) oder den Offline-Modus wählen."
                )
            from .translator_api import ApiTranslator

            return ApiTranslator(
                self.settings.api_key, self.settings.api_model, self.settings.api_endpoint, self.settings.temperature
            )
        from .translator_local import LocalTranslator

        return LocalTranslator(self.settings.resolved_model_path())

    def run(self) -> None:
        from . import document_reader

        try:
            try:
                self._translator = self._make_translator()
            except FileNotFoundError as exc:
                self.failed.emit(f"{exc}\nTipp: Modell laden über Einstellungen → „Modell laden“.")
                return
            except Exception as exc:
                self.failed.emit(str(exc))
                return
            if getattr(self._translator, "gpu_warning", None):
                self.log.emit(f"Warnung: {self._translator.gpu_warning}")

            ocr_backend = self.settings.effective_ocr_backend(self.settings.tool, self.settings.online_enabled)
            if self.settings.ocr_backend == "mistral" and ocr_backend != "mistral":
                self.log.emit("Hinweis: Mistral OCR ist nur im Online-Betrieb verfügbar – lokales OCR wird verwendet.")

            results = []
            total = len(self.paths)
            for i, doc_path in enumerate(self.paths, start=1):
                if self.cancel_event.is_set():
                    break
                self.status.emit(f"Dokument {i}/{total}: {doc_path.name}")
                self.log.emit(f"=== Dokument {i}/{total}: {doc_path.name} ===")

                def _extract_progress(page_nr, page_total, modus, _p=doc_path):
                    if modus == "OCR":
                        self.log.emit(f"{_p.name} – Seite {page_nr}/{page_total}: OCR (gescannte Seite) …")

                try:
                    book = document_reader.read_book(
                        doc_path,
                        ocr=self.settings.ocr_enabled,
                        progress_cb=_extract_progress,
                        ocr_backend=ocr_backend,
                        api_key=self.settings.api_key,
                    )
                    if doc_path.suffix.lower() == ".pdf":
                        self.log.emit(
                            f"PDF geladen: {book.title} – {book.page_count} Seiten, {book.word_count} Wörter, "
                            f"{len(book.chapters)} Kapitel erkannt."
                        )
                    else:
                        self.log.emit(
                            f"Dokument geladen: {book.title} – {book.word_count} Wörter, {len(book.chapters)} Kapitel erkannt."
                        )
                    cache = TranslationCache.load(doc_path) if self.resume else None
                    if cache is not None:
                        self.log.emit(f"Zwischenspeicher für „{doc_path.name}“ gefunden – wird fortgesetzt.")
                    else:
                        cache = TranslationCache(doc_path, TranslationCache.cache_file_for(doc_path), tool=self.settings.tool)
                    cover = pdf_reader.extract_cover_png(doc_path) if doc_path.suffix.lower() == ".pdf" else None
                    pipeline = TranslationPipeline(
                        book=book,
                        translator=self._translator,
                        settings=self.settings,
                        cache=cache,
                        listener=_GuiListener(self),
                        cancel_event=self.cancel_event,
                        glossary=load_glossary(self.settings.glossary_path),
                        cover_png=cover,
                    )
                    result = pipeline.run()
                    results.append({"path": doc_path, "ok": True, "result": result, "error": None})
                    self.log.emit(f"EPUB geschrieben: {result.output_path}")
                except CancelledError:
                    raise
                except Exception as exc:
                    self.log.emit(f"Fehler bei {doc_path.name}: {exc}")
                    results.append({"path": doc_path, "ok": False, "result": None, "error": str(exc)})
            self.finished.emit(results)
        except CancelledError:
            self.cancelled.emit()
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
    """Einstellungen – übersichtlich in Reitern gegliedert und persistiert in settings.json."""

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Einstellungen")
        self.resize(660, 560)

        self.tabs = QTabWidget(self)

        # --- Reiter 1: Allgemein & Modus ---
        tab_general = QWidget()
        layout_general = QVBoxLayout(tab_general)

        grp_look = QGroupBox("Darstellung && Ablage")
        form_look = QFormLayout(grp_look)

        self.cmb_theme = QComboBox()
        for tid, label in theme_mod.THEME_CHOICES:
            self.cmb_theme.addItem(label, tid)
        idx = next((i for i, (tid, _l) in enumerate(theme_mod.THEME_CHOICES) if tid == settings.theme), 0)
        self.cmb_theme.setCurrentIndex(idx)
        form_look.addRow("Design:", self.cmb_theme)

        out_row = QHBoxLayout()
        self.txt_output = QLineEdit(str(settings.resolved_output_dir()))
        btn_out = QPushButton("Wählen …")
        btn_out.clicked.connect(self._pick_output)
        out_row.addWidget(self.txt_output, 1)
        out_row.addWidget(btn_out)
        form_look.addRow("Zielordner (EPUB):", out_row)

        glossar_row = QHBoxLayout()
        self.txt_glossar = QLineEdit(settings.glossary_path)
        self.txt_glossar.setPlaceholderText("Optional: Textdatei mit „Begriff = Übersetzung“ pro Zeile")
        btn_glossar = QPushButton("Wählen …")
        btn_glossar.clicked.connect(self._pick_glossar)
        glossar_row.addWidget(self.txt_glossar, 1)
        glossar_row.addWidget(btn_glossar)
        form_look.addRow("Glossar-Datei:", glossar_row)
        layout_general.addWidget(grp_look)

        grp_mode = QGroupBox("Übersetzungs-Modus")
        form_mode = QFormLayout(grp_mode)

        self.cmb_tool = QComboBox()
        self.cmb_tool.addItem("Offline (lokal auf diesem Gerät, empfohlen)", "offline")
        self.cmb_tool.addItem("Mistral-API (Online-Notnagel)", "api")
        self.cmb_tool.setCurrentIndex(0 if settings.tool == "offline" else 1)
        self.cmb_tool.currentIndexChanged.connect(self._sync_mode_fields)
        form_mode.addRow("Werkzeug:", self.cmb_tool)

        self.chk_online = QCheckBox("Online-Betrieb bewusst einschalten")
        self.chk_online.setChecked(settings.online_enabled)
        self.chk_online.toggled.connect(self._sync_mode_fields)
        self.lbl_online_warning = QLabel(
            "ACHTUNG: Eingeschaltet wird der Buchtext an Mistral (api.mistral.ai) übertragen. "
            "Ohne Häkchen verlässt kein Buchinhalt das Gerät."
        )
        self.lbl_online_warning.setObjectName("hintLabel")
        self.lbl_online_warning.setWordWrap(True)
        form_mode.addRow("Online-Schutz:", self.chk_online)
        form_mode.addRow("", self.lbl_online_warning)

        self.txt_api_key = QLineEdit(settings.api_key)
        self.txt_api_key.setEchoMode(QLineEdit.Password)
        self.txt_api_key.setPlaceholderText("Mistral-API-Schlüssel (nur für Online-Betrieb)")
        form_mode.addRow("API-Schlüssel:", self.txt_api_key)
        self.txt_api_model = QLineEdit(settings.api_model)
        form_mode.addRow("API-Modell:", self.txt_api_model)
        layout_general.addWidget(grp_mode)
        layout_general.addStretch(1)

        # --- Reiter 2: Offline-Modell ---
        tab_model = QWidget()
        layout_model = QVBoxLayout(tab_model)

        grp_model = QGroupBox("Lokales Sprachmodell (GGUF)")
        form_model = QFormLayout(grp_model)

        self.cmb_model = QComboBox()
        for p in MODEL_PRESETS:
            self.cmb_model.addItem(p["label"], p["id"])
        idx = model_preset_index(settings.hf_repo, settings.hf_filename)
        self.cmb_model.setCurrentIndex(idx if idx >= 0 else 0)
        form_model.addRow("Modell-Auswahl:", self.cmb_model)

        model_row = QHBoxLayout()
        self.txt_model = QLineEdit(str(settings.resolved_model_path()))
        btn_model_file = QPushButton("Datei …")
        btn_model_file.clicked.connect(self._pick_model_file)
        model_row.addWidget(self.txt_model, 1)
        model_row.addWidget(btn_model_file)
        form_model.addRow("Modell-Pfad:", model_row)

        self.lbl_model_hint = QLabel("")
        self.lbl_model_hint.setObjectName("hintLabel")
        self.lbl_model_hint.setWordWrap(True)
        form_model.addRow("", self.lbl_model_hint)
        self._update_model_hint()

        self.lbl_model_usage = QLabel("")
        self.lbl_model_usage.setWordWrap(True)
        form_model.addRow("Speicherstatus:", self.lbl_model_usage)

        self._hw_rec = intelligence.recommend_model_preset()
        rec_row = QHBoxLayout()
        self.lbl_hw_recommendation = QLabel(self._hw_rec.reason)
        self.lbl_hw_recommendation.setObjectName("hintLabel")
        self.lbl_hw_recommendation.setWordWrap(True)
        self.btn_apply_recommendation = QPushButton("Empfehlung wählen")
        self.btn_apply_recommendation.setToolTip("Wählt automatisch das für Ihren Rechner empfohlene Modell-Preset aus")
        self.btn_apply_recommendation.clicked.connect(
            lambda: self.cmb_model.setCurrentIndex(self._hw_rec.preset_index)
        )
        rec_row.addWidget(self.lbl_hw_recommendation, 1)
        rec_row.addWidget(self.btn_apply_recommendation, 0, Qt.AlignmentFlag.AlignTop)
        form_model.addRow("Hardware-Tipp:", rec_row)

        model_btn_row = QHBoxLayout()
        self.btn_model_download = QPushButton("Gewähltes Modell laden")
        self.btn_model_download.setObjectName("primaryButton")
        self.btn_model_delete = QPushButton("Modell löschen")
        self.btn_model_download.clicked.connect(self._download_model)
        self.btn_model_delete.clicked.connect(self._delete_model)
        model_btn_row.addWidget(self.btn_model_download)
        model_btn_row.addWidget(self.btn_model_delete)
        model_btn_row.addStretch(1)
        form_model.addRow("", model_btn_row)
        layout_model.addWidget(grp_model)

        grp_wiz = QGroupBox("Einrichtungs-Hilfe")
        wiz_layout = QVBoxLayout(grp_wiz)
        wiz_hint = QLabel("Führt Schritt für Schritt durch die Wahl zwischen Offline-Modell und Online-Notnagel.")
        wiz_hint.setObjectName("hintLabel")
        wiz_hint.setWordWrap(True)
        self.btn_wizard = QPushButton("Erststart-Assistenten erneut öffnen …")
        self.btn_wizard.clicked.connect(self._rerun_wizard)
        wiz_layout.addWidget(wiz_hint)
        wiz_layout.addWidget(self.btn_wizard)
        layout_model.addWidget(grp_wiz)
        layout_model.addStretch(1)

        # --- Reiter 3: Qualität & OCR ---
        tab_quality = QWidget()
        layout_quality = QVBoxLayout(tab_quality)

        grp_quality = QGroupBox("Übersetzungs-Feineinstellungen")
        form_quality = QFormLayout(grp_quality)

        self.spin_temp = QDoubleSpinBox()
        self.spin_temp.setRange(0.0, 1.0)
        self.spin_temp.setSingleStep(0.05)
        self.spin_temp.setValue(settings.temperature)
        self.spin_temp.setToolTip("Niedriger (z. B. 0,2–0,3) = sachlicher und treuer am Original")
        form_quality.addRow("Temperatur:", self.spin_temp)

        self.spin_chunk = QSpinBox()
        self.spin_chunk.setRange(200, 5000)
        self.spin_chunk.setSingleStep(100)
        self.spin_chunk.setValue(settings.chunk_size)
        self.spin_chunk.setToolTip("Größere Abschnitte geben mehr Zusammenhang, brauchen aber mehr Speicher")
        form_quality.addRow("Wörter pro Abschnitt:", self.spin_chunk)
        layout_quality.addWidget(grp_quality)

        grp_ocr = QGroupBox("Texterkennung für gescannte PDFs (OCR)")
        form_ocr = QFormLayout(grp_ocr)

        self.chk_ocr = QCheckBox("Gescannte PDF-Seiten automatisch per OCR erkennen")
        self.chk_ocr.setChecked(settings.ocr_enabled)
        form_ocr.addRow("OCR aktiv:", self.chk_ocr)

        self.cmb_ocr_backend = QComboBox()
        self.cmb_ocr_backend.addItem("Lokal (RapidOCR – kein Datenversand)", "local")
        self.cmb_ocr_backend.addItem("Mistral OCR (nur im Online-Betrieb – Seitenbilder an Mistral)", "mistral")
        self.cmb_ocr_backend.setCurrentIndex(1 if settings.ocr_backend == "mistral" else 0)
        form_ocr.addRow("OCR-Backend:", self.cmb_ocr_backend)
        layout_quality.addWidget(grp_ocr)
        layout_quality.addStretch(1)

        self.tabs.addTab(tab_general, "Allgemein && Modus")
        self.tabs.addTab(tab_model, "Offline-Modell")
        self.tabs.addTab(tab_quality, "Qualität && OCR")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_ok = buttons.button(QDialogButtonBox.Ok)
        if btn_ok is not None:
            btn_ok.setText("Speichern")
            btn_ok.setObjectName("primaryButton")
        btn_cancel = buttons.button(QDialogButtonBox.Cancel)
        if btn_cancel is not None:
            btn_cancel.setText("Abbrechen")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs, 1)
        layout.addWidget(buttons)
        self._sync_mode_fields()
        self._refresh_usage()

    def _sync_mode_fields(self) -> None:
        is_api = self.cmb_tool.currentData() == "api"
        online = self.chk_online.isChecked()
        self.txt_api_key.setEnabled(is_api or online)
        self.txt_api_model.setEnabled(is_api or online)

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
        state = "Bereit (lokal vorhanden)" if model_manager.is_model_present(model_path) else "Noch nicht heruntergeladen"
        self.lbl_model_usage.setText(
            f"{state}\nPfad: {model_path}\nBelegt: {model_manager.format_bytes(usage)} – "
            f"frei auf Laufwerk: {model_manager.format_bytes(free)}"
        )

    def _update_model_hint(self) -> None:
        current = self.settings.resolved_model_path().name
        if current in LEGACY_HF_FILENAMES:
            self.lbl_model_hint.setText(
                "Hinweis: Es ist ein älteres Modell geladen. Für deutlich bessere Übersetzungen "
                "oben ein aktuelles Modell wählen und „Gewähltes Modell laden“ klicken."
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
        s.theme = self.cmb_theme.currentData()
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
        self.resize(540, 320)
        layout = QVBoxLayout(self)

        grp = QGroupBox("Ergebnis Ihres Tolino-EPUBs")
        grp_layout = QVBoxLayout(grp)
        text = QLabel()
        lines = [
            f"• Seiten: {result.pages}   |   Wörter: {result.words}",
            f"• Abschnitte: {result.chunks_done} übersetzt, {result.chunks_failed} fehlgeschlagen (von {result.chunks_total})",
            f"• Dauer: {fmt_duration(result.duration_seconds)}",
        ]
        if tool == "api":
            lines.append(f"• An Mistral gesendete Zeichen: {result.chars_sent} (für die Kostenschätzung)")
        lines.append(f"\nGespeichert unter:\n{result.output_path}")
        text.setText("\n".join(lines))
        text.setWordWrap(True)
        grp_layout.addWidget(text)
        layout.addWidget(grp, 1)

        row = QHBoxLayout()
        row.addStretch(1)
        btn_open = QPushButton("Ablageordner öffnen")
        btn_open.setObjectName("primaryButton")
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
        self.setWindowTitle(theme_mod.window_title(settings.theme))
        self.resize(840, 680)
        self.setAcceptDrops(True)
        self._worker: _Worker | None = None

        central = QWidget(self)
        central.setObjectName("central")  # transparent, damit der Farbverlauf des Fensters sichtbar bleibt
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # --- Kopfbereich: Titel, saisonaler Gruß und Schnellzugriffe ---
        header_row = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.lbl_title = QLabel("Gideon's Übersetzer")
        self.lbl_title.setObjectName("headerTitle")
        self.lbl_subtitle = QLabel("Englische Bücher (PDF, EPUB, DOCX) ins Deutsche übersetzen → Tolino-EPUB")
        self.lbl_subtitle.setObjectName("headerSubtitle")
        title_col.addWidget(self.lbl_title)
        title_col.addWidget(self.lbl_subtitle)
        header_row.addLayout(title_col, 1)

        # saisonaler Gruß (z. B. "🍂 Herbst") als Pill-Badge im automatischen Design
        self.lbl_season = QLabel(theme_mod.season_label(settings.theme))
        self.lbl_season.setObjectName("seasonBadge")
        self.lbl_season.setVisible(bool(self.lbl_season.text()))
        header_row.addWidget(self.lbl_season, 0, Qt.AlignmentFlag.AlignVCenter)

        btn_update = QPushButton("Update …")
        btn_update.setToolTip("Manuell nach neuer Version auf GitHub suchen (kontaktiert api.github.com)")
        btn_update.clicked.connect(self._check_update)
        btn_report = QPushButton("Diagnose-Report …")
        btn_report.setToolTip("Diagnose-Report als Markdown-Datei speichern (kein API-Schlüssel, keine Buchinhalte)")
        btn_report.clicked.connect(self._create_report)
        btn_settings = QPushButton("Einstellungen …")
        btn_settings.setToolTip("Design, Offline-Modell, Online-Notnagel und OCR konfigurieren")
        btn_settings.clicked.connect(self._open_settings)
        header_row.addWidget(btn_update, 0, Qt.AlignmentFlag.AlignVCenter)
        header_row.addWidget(btn_report, 0, Qt.AlignmentFlag.AlignVCenter)
        header_row.addWidget(btn_settings, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(header_row)

        # --- Schritt 1: Dokumente auswählen (Warteschlange) ---
        self.grp_queue = QGroupBox("1. Dokumente auswählen (Warteschlange)")
        queue_layout = QVBoxLayout(self.grp_queue)
        queue_layout.setSpacing(6)

        self.lbl_drop_hint = QLabel(
            "Tipp: Dateien einfach per Drag & Drop hierher ziehen oder über „+ Dokumente hinzufügen …“ auswählen. "
            "Mehrere Bücher werden automatisch nacheinander übersetzt."
        )
        self.lbl_drop_hint.setObjectName("hintLabel")
        self.lbl_drop_hint.setWordWrap(True)
        queue_layout.addWidget(self.lbl_drop_hint)

        queue_row = QHBoxLayout()
        self.list_files = QListWidget()
        self.list_files.setToolTip("Dokumente in dieser Reihenfolge zur Warteschlange hinzufügen (PDF, EPUB, DOCX)")
        self.list_files.setMinimumHeight(110)

        queue_btns = QVBoxLayout()
        queue_btns.setSpacing(6)
        self.btn_add = QPushButton("+ Dokumente hinzufügen …")
        self.btn_add.clicked.connect(self._add_files)
        self.btn_remove = QPushButton("Auswahl entfernen")
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_clear = QPushButton("Liste leeren")
        self.btn_clear.clicked.connect(self.list_files.clear)
        for b in (self.btn_add, self.btn_remove, self.btn_clear):
            queue_btns.addWidget(b)
        queue_btns.addStretch(1)

        queue_row.addWidget(self.list_files, 1)
        queue_row.addLayout(queue_btns)
        queue_layout.addLayout(queue_row)
        layout.addWidget(self.grp_queue)

        # --- Schritt 2: Ausgabe & Optionen ---
        self.grp_options = QGroupBox("2. Ausgabe && Übersetzungsmodus")
        opts_form = QFormLayout(self.grp_options)
        opts_form.setSpacing(8)

        out_row = QHBoxLayout()
        self.txt_output = QLineEdit(str(settings.resolved_output_dir()))
        self.txt_output.setToolTip("Hier werden die fertigen deutschen EPUB-Dateien abgelegt")
        btn_out = QPushButton("Ordner wählen …")
        btn_out.clicked.connect(lambda: self._pick_dir(self.txt_output))
        btn_open_out = QPushButton("Ordner öffnen")
        btn_open_out.setToolTip("Zielordner im Datei-Explorer öffnen")
        btn_open_out.clicked.connect(self._open_output_dir)
        out_row.addWidget(self.txt_output, 1)
        out_row.addWidget(btn_out)
        out_row.addWidget(btn_open_out)
        opts_form.addRow("Zielordner (EPUB):", out_row)

        glossar_row = QHBoxLayout()
        self.txt_glossar = QLineEdit(settings.glossary_path)
        self.txt_glossar.setPlaceholderText("Optional: eigene Wortliste („Begriff = Übersetzung“ pro Zeile)")
        btn_glossar = QPushButton("Datei wählen …")
        btn_glossar.clicked.connect(
            lambda: self._pick_file(self.txt_glossar, "Glossar wählen", "Textdateien (*.txt);;Alle (*)")
        )
        glossar_row.addWidget(self.txt_glossar, 1)
        glossar_row.addWidget(btn_glossar)
        opts_form.addRow("Glossar (optional):", glossar_row)

        mode_row = QHBoxLayout()
        self.lbl_tool = QLabel()
        self.lbl_tool.setObjectName("modeBadge")
        btn_change_mode = QPushButton("Modus / Modell ändern …")
        btn_change_mode.clicked.connect(self._open_settings)
        mode_row.addWidget(self.lbl_tool, 1)
        mode_row.addWidget(btn_change_mode)
        opts_form.addRow("Aktives Werkzeug:", mode_row)
        layout.addWidget(self.grp_options)

        # --- Schritt 3: Start & Fortschritt ---
        self.grp_run = QGroupBox("3. Übersetzung && Live-Einblick")
        run_layout = QVBoxLayout(self.grp_run)
        run_layout.setSpacing(8)

        action_row = QHBoxLayout()
        self.btn_start = QPushButton("Übersetzen starten")
        self.btn_start.setObjectName("primaryButton")
        self.btn_start.clicked.connect(self._start)
        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel)
        action_row.addWidget(self.btn_start)
        action_row.addWidget(self.btn_cancel)
        action_row.addSpacing(10)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        action_row.addWidget(self.progress, 1)
        run_layout.addLayout(action_row)

        status_row = QHBoxLayout()
        self.lbl_status = QLabel("Bereit – Dokumente hinzufügen und „Übersetzen starten“ klicken.")
        self.lbl_eta = QLabel("")
        self.lbl_eta.setObjectName("hintLabel")
        status_row.addWidget(self.lbl_status, 1)
        status_row.addWidget(self.lbl_eta)
        run_layout.addLayout(status_row)

        # Reiter für Live-Textprobe und Protokoll (spart Platz, kein gequetschtes Doppelfeld)
        self.output_tabs = QTabWidget()
        self.txt_preview = QPlainTextEdit()
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setPlaceholderText("Hier erscheint während der Übersetzung live der deutsche Text des aktuellen Abschnitts …")
        self.txt_log = QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setMaximumBlockCount(500)
        self.txt_log.setPlaceholderText("Schritte, Kapitel-Erkennung und Hinweise werden hier protokolliert …")
        self.output_tabs.addTab(self.txt_preview, "Live-Textprobe (aktueller Abschnitt)")
        self.output_tabs.addTab(self.txt_log, "Protokoll && Details")
        run_layout.addWidget(self.output_tabs, 1)
        layout.addWidget(self.grp_run, 1)

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
                f"Mistral-API (Online-Betrieb: {state}) – "
                + ("sendet Buchtext an Mistral!" if self.settings.online_enabled else "nicht aktiv")
            )
        else:
            model_path = self.settings.resolved_model_path()
            present = model_manager.is_model_present(model_path)
            status_str = f"Modell bereit ({model_path.name})" if present else "Modell noch nicht geladen"
            self.lbl_tool.setText(f"OFFLINE (lokal, empfohlen) – {status_str} · kein Buchinhalt verlässt das Gerät")

    def _open_output_dir(self) -> None:
        folder = Path(self.txt_output.text().strip() or str(self.settings.resolved_output_dir()))
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    # --- Datei-Dialoge / Drag & Drop ---

    def _add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Englische Dokumente zur Warteschlange hinzufügen", "",
            "Dokumente (*.pdf *.epub *.docx);;Alle Dateien (*)",
        )
        for p in paths:
            if not self.list_files.findItems(p, Qt.MatchFlag.MatchExactly):
                self.list_files.addItem(p)

    def _remove_selected(self) -> None:
        for item in self.list_files.selectedItems():
            self.list_files.takeItem(self.list_files.row(item))
        self._refresh_queue_summary()

    def _clear_files(self) -> None:
        self.list_files.clear()
        self._refresh_queue_summary()

    def _refresh_queue_summary(self) -> None:
        paths = [Path(self.list_files.item(i).text()) for i in range(self.list_files.count())]
        if not paths:
            self.lbl_queue_summary.setText("Noch keine Dokumente in der Warteschlange.")
            return
        summary = intelligence.summarize_queue(paths, cache_loader=TranslationCache.load)
        parts = [
            f"{summary.file_count} Dokument(e)",
            f"gesamt {model_manager.format_bytes(summary.total_bytes)}",
        ]
        if summary.cached_count:
            parts.append(f"{summary.cached_count} mit Zwischenspeicher (fortsetzbar)")
        if summary.missing_count:
            parts.append(f"{summary.missing_count} Datei(en) nicht gefunden")
        self.lbl_queue_summary.setText("Warteschlange: " + " · ".join(parts))

    def _pick_file(self, edit: QLineEdit, title: str, filt: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, title, "", filt)
        if path:
            edit.setText(path)

    def _pick_dir(self, edit: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, "Zielordner wählen", edit.text())
        if path:
            edit.setText(path)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls() and any(
            u.toLocalFile().lower().endswith((".pdf", ".epub", ".docx")) for u in event.mimeData().urls()
        ):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        added = False
        for url in event.mimeData().urls():
            local = url.toLocalFile()
            if local.lower().endswith((".pdf", ".epub", ".docx")):
                if not self.list_files.findItems(local, Qt.MatchFlag.MatchExactly):
                    self.list_files.addItem(local)
                added = True
        if added:
            event.acceptProposedAction()

    # --- Einstellungen ---

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec() == QDialog.Accepted:
            self.txt_glossar.setText(self.settings.glossary_path)
            self.txt_output.setText(str(self.settings.resolved_output_dir()))
            self._refresh_tool_label()
            # Design live übernehmen (saisonale Palette, Fenstertitel, Gruß-Label)
            if QApplication.instance() is not None:
                theme_mod.apply_theme(QApplication.instance(), self.settings.theme)
            self.setWindowTitle(theme_mod.window_title(self.settings.theme))
            self.lbl_season.setText(theme_mod.season_label(self.settings.theme))
            self.lbl_season.setVisible(bool(self.lbl_season.text()))

    # --- Übersetzung starten / abbrechen ---

    def _start(self) -> None:
        paths = [Path(self.list_files.item(i).text()) for i in range(self.list_files.count())]
        paths = [p for p in paths if p.is_file()]
        if not paths:
            QMessageBox.warning(self, "Keine Dokumente", "Bitte zuerst englische Dokumente (PDF/EPUB/DOCX) zur Warteschlange hinzufügen.")
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

        resume = True
        existing = [p for p in paths if TranslationCache.load(p) is not None]
        if existing:
            answer = QMessageBox.question(
                self, "Übersetzung fortsetzen?",
                f"Für {len(existing)} Dokument(e) existiert ein Zwischenspeicher mit bereits übersetzten Abschnitten.\n\n"
                "Soll fortgesetzt werden?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
            )
            resume = answer == QMessageBox.Yes

        self.txt_preview.clear()
        self.txt_log.clear()
        self.progress.setValue(0)
        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.lbl_status.setText(f"Warteschlange: {len(paths)} Dokument(e) …")

        self._worker = _Worker(paths, self.settings, self, resume=resume)
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

    def _on_finished(self, results) -> None:
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.lbl_eta.setText("")
        ok = [r for r in results if r["ok"]]
        failed = [r for r in results if not r["ok"]]
        self.lbl_status.setText(f"Fertig: {len(ok)}/{len(results)} erfolgreich.")
        if len(results) == 1 and ok:
            result = ok[0]["result"]
            self.txt_log.appendPlainText("EPUB geschrieben: " + str(result.output_path))
            dlg = SummaryDialog(result, self.settings.tool, self)
            dlg.exec()
            return
        lines = []
        for r in results:
            if r["ok"]:
                lines.append(f"OK: {r['path'].name} → {r['result'].output_path.name}")
            else:
                lines.append(f"FEHLER: {r['path'].name} – {r['error']}")
        QMessageBox.information(
            self, "Warteschlange fertig",
            f"{len(ok)}/{len(results)} erfolgreich, {len(failed)} fehlgeschlagen.\n\n" + "\n".join(lines),
        )

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
