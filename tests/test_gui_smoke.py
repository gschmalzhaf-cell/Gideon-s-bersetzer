"""GUI-Smoke-Tests (laufen nur, wenn PySide6 samt Systembibliotheken verfügbar ist,
z. B. auf einem Windows-Entwicklungsrechner; in headless-CI ohne Qt-Libs werden sie übersprungen)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication  # noqa: E402
except ImportError as exc:  # Qt-Systembibliotheken fehlen (z. B. headless ohne libGL)
    pytest.skip(f"PySide6 nicht importierbar: {exc}", allow_module_level=True)

from PySide6.QtWidgets import QApplication  # noqa: E402

from gideons_uebersetzer.main_window import MainWindow, SettingsDialog, SummaryDialog  # noqa: E402
from gideons_uebersetzer.settings import Settings  # noqa: E402
from gideons_uebersetzer.wizard import FirstStartWizard  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_main_window_builds(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr("gideons_uebersetzer.settings.default_settings_path", lambda: tmp_path / "settings.json")
    settings = Settings(output_dir=str(tmp_path))
    win = MainWindow(settings)
    assert win.windowTitle() == "Gideon's Übersetzer"
    assert win.btn_start.isEnabled()
    assert not win.btn_cancel.isEnabled()
    assert "OFFLINE" in win.lbl_tool.text()
    win.close()


def test_wizard_builds(qapp):
    settings = Settings()
    wiz = FirstStartWizard(settings)
    assert len(wiz.pageIds()) == 4
    assert wiz.mode_page.radio_offline.isChecked()  # Offline an erster Stelle vorausgewählt
    wiz.close()


def test_settings_dialog_builds(qapp, tmp_path):
    settings = Settings()
    dlg = SettingsDialog(settings)
    assert dlg.cmb_tool.currentData() == "offline"
    assert dlg.spin_temp.value() == pytest.approx(0.3)
    assert dlg.spin_chunk.value() == 1500
    assert not dlg.chk_online.isChecked()  # Online-Betrieb standardmäßig aus
    dlg.close()


def test_summary_dialog(qapp, tmp_path):
    class R:
        pages = 100
        words = 50000
        chunks_done = 33
        chunks_failed = 0
        chunks_total = 33
        duration_seconds = 600
        chars_sent = 123456
        output_path = tmp_path / "buch (deutsch).epub"

    dlg = SummaryDialog(R(), "api")
    dlg.close()
