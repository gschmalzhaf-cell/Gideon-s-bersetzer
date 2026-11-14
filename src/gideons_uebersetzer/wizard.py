"""Erststart-Assistent: OFFLINE steht an erster Stelle (Standard), der
Online-Notnagel (Mistral-API) ist optional und wird nur nach bewusstem
Einschalten aktiv. In maximal zwei Klicks ist der Offline-Weg betriebsbereit:
"Weiter" (Offline ist vorausgewählt) → "Modell jetzt laden".
"""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from . import model_manager
from .settings import Settings, save_settings


class DownloadWorker(QObject):
    progress = Signal(int, int, float)  # bytes, gesamt, tempo
    finished = Signal(str)  # pfad
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        try:
            dest = model_manager.download_model(
                self.settings.hf_repo,
                self.settings.hf_filename,
                self.settings.resolved_model_path().parent,
                progress_cb=lambda d, t, s: self.progress.emit(d, t, s),
                cancel_event=self.cancel_event,
            )
        except model_manager.DownloadCancelled:
            self.cancelled.emit()
            return
        except model_manager.ModelError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:  # nie einen nackten Traceback zeigen
            self.failed.emit(f"Unerwarteter Fehler beim Modell-Download: {exc}")
            return
        self.finished.emit(str(dest))


class ModelPage(QWizardPage):
    """Seite zum einmaligen Modell-Download (Offline-Weg)."""

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setTitle("Offline-Modell laden")
        self.setSubTitle("Einmalig ca. 4–5 GB von Hugging Face – danach läuft alles lokal ohne Internet.")

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.btn_download = QPushButton("Modell jetzt laden")
        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.setVisible(False)
        self.btn_download.clicked.connect(self._start_download)
        self.btn_cancel.clicked.connect(self._cancel_download)
        self._worker = None
        self._thread = None

        layout = QVBoxLayout(self)
        layout.addWidget(self.info_label)
        layout.addWidget(self.progress)
        layout.addWidget(self.status_label)
        row = QHBoxLayout()
        row.addWidget(self.btn_download)
        row.addWidget(self.btn_cancel)
        layout.addLayout(row)
        self._update_info()

    def _update_info(self) -> None:
        model_path = self.settings.resolved_model_path()
        try:
            info = model_manager.model_file_info(self.settings.hf_repo, self.settings.hf_filename)
            size = model_manager.format_bytes(info["size"])
        except model_manager.ModelError as exc:
            size = f"(Größe unbekannt: {exc})"
        if model_manager.is_model_present(model_path):
            self.info_label.setText(
                f"Modell ist bereits vorhanden:\n{model_path}\n"
                f"Belegt: {model_manager.format_bytes(model_manager.model_disk_usage(model_path))}"
            )
            self.btn_download.setText("Erneut laden (falls beschädigt)")
        else:
            parent = model_path.parent if model_path.parent.exists() else Path.home()
            free = model_manager.free_space_bytes(parent)
            self.info_label.setText(
                f"Modell: {self.settings.hf_repo} / {self.settings.hf_filename}\n"
                f"Größe: ca. {size} – Ziel: {model_path}\n"
                f"Freier Speicherplatz: {model_manager.format_bytes(free)}\n\n"
                "Der Download kann jederzeit abgebrochen und später fortgesetzt werden."
            )

    def _start_download(self) -> None:
        self.btn_download.setEnabled(False)
        self.progress.setVisible(True)
        self.btn_cancel.setVisible(True)
        self.status_label.setText("Download läuft …")
        self._worker = DownloadWorker(self.settings)
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self._thread.start()

    def _cancel_download(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def _on_progress(self, done: int, total: int, speed: float) -> None:
        self.progress.setMaximum(total)
        self.progress.setValue(done)
        eta = (total - done) / speed if speed > 0 else 0
        self.status_label.setText(
            f"{model_manager.format_bytes(done)} von {model_manager.format_bytes(total)} "
            f"({model_manager.format_bytes(speed)}/s, geschätzt noch {int(eta)} s)"
        )

    def _on_finished(self, path: str) -> None:
        self.progress.setMaximum(1)
        self.progress.setValue(1)
        self.status_label.setText(f"Modell bereit: {path}")
        self.btn_cancel.setVisible(False)
        self.btn_download.setEnabled(True)
        self.btn_download.setText("Erneut laden")
        self._thread.quit()

    def _on_failed(self, message: str) -> None:
        self.status_label.setText(f"Fehler: {message}")
        self.btn_cancel.setVisible(False)
        self.btn_download.setEnabled(True)
        QMessageBox.warning(self, "Modell-Download fehlgeschlagen", message)
        self._thread.quit()

    def _on_cancelled(self) -> None:
        self.status_label.setText("Abgebrochen. Die bereits geladenen Daten bleiben erhalten – später fortsetzbar.")
        self.btn_cancel.setVisible(False)
        self.btn_download.setEnabled(True)
        self._thread.quit()


class ModePage(QWizardPage):
    """Wahl des Werkzeugs: OFFLINE (Standard, erste Stelle) oder NOTNAGEL (API)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Wie soll übersetzt werden?")
        self.setSubTitle("Der Offline-Weg ist empfohlen und an erster Stelle vorausgewählt.")

        self.radio_offline = QRadioButton("OFFLINE (empfohlen, Standard)")
        self.radio_offline.setChecked(True)
        offline_desc = QLabel(
            "Die Anwendung lädt ihr Übersetzungsmodell einmalig herunter (ca. 4–5 GB) "
            "und übersetzt danach vollständig lokal auf Ihrem Gerät. Kein Internet nötig, "
            "kein API-Schlüssel nötig. Kein Buchinhalt verlässt Ihr Gerät."
        )
        offline_desc.setWordWrap(True)
        offline_desc.setIndent(20)

        self.radio_online = QRadioButton("NOTNAGEL: Mistral-API (Online-Betrieb)")
        online_desc = QLabel(
            "ACHTUNG: In diesem Modus wird der Buchtext an Mistral (api.mistral.ai) übertragen. "
            "Er ist nur nach Ihrem bewussten Einschalten aktiv und niemals automatisch."
        )
        online_desc.setWordWrap(True)
        online_desc.setIndent(20)

        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("Mistral-API-Schlüssel (optional, nur für den Online-Betrieb)")
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.model_edit = QLineEdit("mistral-small-latest")
        self.key_edit.setEnabled(False)
        self.model_edit.setEnabled(False)

        self.radio_offline.toggled.connect(self._update_enabled)
        self.radio_online.toggled.connect(self._update_enabled)

        layout = QVBoxLayout(self)
        layout.addWidget(self.radio_offline)
        layout.addWidget(offline_desc)
        layout.addSpacing(12)
        layout.addWidget(self.radio_online)
        layout.addWidget(online_desc)
        layout.addSpacing(8)
        layout.addWidget(QLabel("API-Schlüssel:"))
        layout.addWidget(self.key_edit)
        layout.addWidget(QLabel("API-Modell:"))
        layout.addWidget(self.model_edit)

    def _update_enabled(self) -> None:
        online = self.radio_online.isChecked()
        self.key_edit.setEnabled(online)
        self.model_edit.setEnabled(online)

    def apply_to(self, settings: Settings) -> None:
        if self.radio_offline.isChecked():
            settings.tool = "offline"
            settings.online_enabled = False
        else:
            settings.tool = "api"
            settings.online_enabled = True
            settings.api_key = self.key_edit.text().strip()
            settings.api_model = self.model_edit.text().strip() or "mistral-small-latest"


class FirstStartWizard(QWizard):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Erststart-Assistent – Gideon's Übersetzer")
        self.setWizardStyle(QWizard.ModernStyle)

        intro = QWizardPage()
        intro.setTitle("Willkommen bei Gideon's Übersetzer")
        intro_text = QLabel(
            "Diese Anwendung übersetzt englischsprachige PDFs ins Deutsche und erzeugt "
            "eine EPUB-Datei für Ihren Tolino.\n\n"
            "Standardmäßig arbeitet sie OFFLINE: Das Übersetzungsmodell wird einmalig "
            "heruntergeladen und liegt dann lokal auf Ihrem Gerät. Ohne eingeschalteten "
            "Online-Betrieb verlässt kein Buchinhalt das Gerät.\n\n"
            "Im nächsten Schritt wählen Sie den Weg – Offline ist vorausgewählt."
        )
        intro_text.setWordWrap(True)
        intro_layout = QVBoxLayout(intro)
        intro_layout.addWidget(intro_text)

        self.mode_page = ModePage()
        self.model_page = ModelPage(settings)

        self.addPage(intro)
        self.addPage(self.mode_page)
        self.addPage(self.model_page)

        finish = QWizardPage()
        finish.setTitle("Fertig")
        finish.setFinalPage(True)
        finish_text = QLabel(
            "Sie sind startklar.\n\n"
            "• Offline: Sobald das Modell geladen ist, können Sie ein PDF wählen und übersetzen – "
            "komplett ohne Internet.\n"
            "• Online (nur falls eingeschaltet): Tragen Sie Ihren API-Schlüssel in den "
            "Einstellungen ein.\n\n"
            "Die Einstellungen können jederzeit über „Einstellungen …“ im Hauptfenster geändert werden."
        )
        finish_text.setWordWrap(True)
        finish_layout = QVBoxLayout(finish)
        finish_layout.addWidget(finish_text)
        self.addPage(finish)

    def accept(self) -> None:
        self.mode_page.apply_to(self.settings)
        if self.settings.tool == "offline" and not model_manager.is_model_present(self.settings.resolved_model_path()):
            answer = QMessageBox.question(
                self,
                "Modell noch nicht geladen",
                "Das Offline-Modell ist noch nicht heruntergeladen. Ohne Modell kann nicht offline "
                "übersetzt werden.\n\nJetzt laden oder später in den Einstellungen nachholen?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer == QMessageBox.Yes:
                self.setCurrentId(2)  # zurück zur Modell-Seite
                return
        self.settings.first_start_done = True
        save_settings(self.settings)
        super().accept()
