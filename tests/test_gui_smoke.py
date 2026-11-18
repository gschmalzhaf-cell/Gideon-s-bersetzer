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


@pytest.fixture(scope="session", autouse=True)
def _qt_session_cleanup():
    """Qt kontrolliert abbauen, BEVOR der Interpreter endet.

    Ohne explizites Schließen/Loeschen der QApplication (und ihrer Fenster) kann der
    Prozess beim Herunterfahren mit einer Zugriffsverletzung (0xC0000005) crashen,
    was in CI als mysteriöser Exitcode 1 nach "alle Tests bestanden" sichtbar wird.
    """
    yield
    import gc

    app = QApplication.instance()
    if app is not None:
        app.closeAllWindows()
        app.processEvents()
        app.quit()
        app.processEvents()
        try:
            import shiboken6

            shiboken6.delete(app)
        except Exception:
            pass
        gc.collect()


def test_main_window_builds(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr("gideons_uebersetzer.settings.default_settings_path", lambda: tmp_path / "settings.json")
    settings = Settings(output_dir=str(tmp_path))
    win = MainWindow(settings)
    assert "Gideon's Übersetzer" in win.windowTitle()  # saisonaler Modus hängt ein Emoji davor
    assert win.btn_start.isEnabled()
    assert not win.btn_cancel.isEnabled()
    assert "OFFLINE" in win.lbl_tool.text()
    win.close()
    win.deleteLater()
    qapp.processEvents()


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
    dlg.deleteLater()
    qapp.processEvents()


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
    dlg.deleteLater()
    qapp.processEvents()


def test_live_preview_appends(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr("gideons_uebersetzer.settings.default_settings_path", lambda: tmp_path / "settings.json")
    win = MainWindow(Settings(output_dir=str(tmp_path)))
    win._append_preview("Hallo ")
    win._append_preview("Welt!")
    assert "Hallo Welt!" in win.txt_preview.toPlainText()
    win.close()
    win.deleteLater()
    qapp.processEvents()


def test_settings_dialog_has_model_presets(qapp):
    dlg = SettingsDialog(Settings())
    assert dlg.cmb_model.count() >= 3
    assert dlg.cmb_model.currentData() == "qwen2.5-7b"
    dlg.close()
    dlg.deleteLater()
    qapp.processEvents()


def test_main_window_has_queue_list(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr("gideons_uebersetzer.settings.default_settings_path", lambda: tmp_path / "settings.json")
    win = MainWindow(Settings(output_dir=str(tmp_path)))
    assert win.list_files.count() == 0
    win.list_files.addItem(str(tmp_path / "a.pdf"))
    win.list_files.addItem(str(tmp_path / "b.epub"))
    assert win.list_files.count() == 2
    win._remove_selected.__self__  # Methode existiert
    win.close()
    win.deleteLater()
    qapp.processEvents()


def test_theme_applied_and_season_label(qapp, tmp_path, monkeypatch):
    from gideons_uebersetzer import theme

    monkeypatch.setattr("gideons_uebersetzer.settings.default_settings_path", lambda: tmp_path / "settings.json")
    theme.apply_theme(qapp, "seasonal")  # so macht es app.py beim Start
    assert "border-radius" in qapp.styleSheet()
    win = MainWindow(Settings(output_dir=str(tmp_path)))  # Default: saisonal
    assert win.lbl_season.text() != ""  # z. B. "🍂 Herbst"
    win.close()
    win.deleteLater()
    qapp.processEvents()

    win2 = MainWindow(Settings(output_dir=str(tmp_path), theme="dark"))
    assert win2.windowTitle() == "Gideon's Übersetzer"  # kein Emoji im festen Modus
    assert win2.lbl_season.text() == ""
    theme.apply_theme(qapp, "dark")  # live-Übernahme wie nach Einstellungs-OK in _open_settings
    assert theme.PALETTES["dark"]["accent"] in qapp.styleSheet()
    win2.close()
    win2.deleteLater()
    qapp.processEvents()

    dlg = SettingsDialog(Settings())
    assert dlg.cmb_theme.count() == 3
    assert dlg.cmb_theme.currentData() == "seasonal"
    dlg.close()
    dlg.deleteLater()
    qapp.processEvents()
