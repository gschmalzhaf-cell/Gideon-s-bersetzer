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
    rc = cli.main(["uebersetzen", str(scanned_pdf), "--no-resume"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "keine Textebene" in out
    assert "OCR ist in Version 1 nicht enthalten" in out
