import json
import zipfile

from gideons_uebersetzer import cli, settings as settings_mod
from gideons_uebersetzer.cache import TranslationCache


def test_cli_modell_info(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(settings_mod, "default_settings_path", lambda: tmp_path / "settings.json")
    monkeypatch.setattr(settings_mod, "app_data_dir", lambda: tmp_path)
    rc = cli.main(["modell", "info"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Kein Modell installiert" in out


def test_cli_uebersetzen_with_fake_translator(monkeypatch, tmp_path, sample_pdf, capsys):
    monkeypatch.setattr(settings_mod, "default_settings_path", lambda: tmp_path / "settings.json")
    monkeypatch.setattr(settings_mod, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(settings_mod, "default_output_dir", lambda: tmp_path / "out")

    from test_pipeline import ScriptedTranslator

    monkeypatch.setattr(cli, "_build_translator", lambda args, settings: (ScriptedTranslator(), "offline"))
    rc = cli.main(["uebersetzen", str(sample_pdf), "--no-resume", "--no-cover"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Zusammenfassung" in out
    assert "Ausgabedatei" in out
    epub_files = list((tmp_path / "out").glob("*.epub"))
    assert len(epub_files) == 1
    assert epub_files[0].name.endswith("(deutsch).epub")
    with zipfile.ZipFile(epub_files[0]) as zf:
        assert "META-INF/container.xml" in zf.namelist()


def test_cli_scanned_pdf_message(monkeypatch, tmp_path, scanned_pdf, capsys):
    monkeypatch.setattr(settings_mod, "default_settings_path", lambda: tmp_path / "settings.json")
    monkeypatch.setattr(settings_mod, "app_data_dir", lambda: tmp_path)
    rc = cli.main(["uebersetzen", str(scanned_pdf), "--no-resume", "--no-ocr"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "keine Textebene" in out
    assert "OCR ist ausgeschaltet" in out


def test_cli_queue_processes_multiple_documents(monkeypatch, tmp_path, sample_pdf, capsys):
    monkeypatch.setattr(settings_mod, "default_settings_path", lambda: tmp_path / "settings.json")
    monkeypatch.setattr(settings_mod, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(settings_mod, "default_output_dir", lambda: tmp_path / "out")

    from test_pipeline import ScriptedTranslator

    built = []
    def fake_build(args, settings):
        built.append(1)
        return (ScriptedTranslator(), "offline")
    monkeypatch.setattr(cli, "_build_translator", fake_build)

    second = tmp_path / "second.pdf"
    second.write_bytes(sample_pdf.read_bytes())
    rc = cli.main(["uebersetzen", str(sample_pdf), str(second), "--no-resume", "--no-cover"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Dokument 1/2" in out and "Dokument 2/2" in out
    assert "Warteschlange fertig: 2/2 erfolgreich" in out
    assert len(built) == 1  # Translator wird nur einmal geladen
    assert len(list((tmp_path / "out").glob("*.epub"))) == 1  # gleiche Quelle -> gleiche Ausgabedatei


def test_cli_queue_continues_after_failure(monkeypatch, tmp_path, sample_pdf, capsys):
    monkeypatch.setattr(settings_mod, "default_settings_path", lambda: tmp_path / "settings.json")
    monkeypatch.setattr(settings_mod, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(settings_mod, "default_output_dir", lambda: tmp_path / "out")

    from test_pipeline import ScriptedTranslator

    monkeypatch.setattr(cli, "_build_translator", lambda args, settings: (ScriptedTranslator(), "offline"))
    broken = tmp_path / "broken.txt"
    broken.write_text("nope", encoding="utf-8")
    rc = cli.main(["uebersetzen", str(broken), str(sample_pdf), "--no-resume", "--no-cover"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "Fehler" in out
    assert "Warteschlange fertig: 1/2 erfolgreich" in out
