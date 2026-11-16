import re

from gideons_uebersetzer import settings


def test_default_hf_filename_uses_current_hf_naming():
    assert settings.DEFAULT_HF_FILENAME == "Mistral-7B-Instruct-v0.3-Q4_K_M.gguf"
    assert re.fullmatch(r"Mistral-7B-Instruct-v0\.3-Q\d_K_\w+\.gguf", settings.DEFAULT_HF_FILENAME)


def test_default_model_path_prefers_new_file(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    models = tmp_path / "Tolino-Uebersetzer" / "models"
    models.mkdir(parents=True)
    (models / settings.DEFAULT_HF_FILENAME).write_bytes(b"x")
    (models / settings.LEGACY_HF_FILENAME).write_bytes(b"x")
    assert settings.default_model_path().name == settings.DEFAULT_HF_FILENAME


def test_default_model_path_falls_back_to_legacy_file(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    models = tmp_path / "Tolino-Uebersetzer" / "models"
    models.mkdir(parents=True)
    (models / settings.LEGACY_HF_FILENAME).write_bytes(b"x")
    assert settings.default_model_path().name == settings.LEGACY_HF_FILENAME


def test_load_settings_resets_legacy_filename_when_file_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    path = tmp_path / "settings.json"
    path.write_text('{"hf_filename": "%s"}' % settings.LEGACY_HF_FILENAME, encoding="utf-8")
    assert settings.load_settings(path).hf_filename == settings.DEFAULT_HF_FILENAME


def test_load_settings_keeps_legacy_filename_when_file_present(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    models = tmp_path / "Tolino-Uebersetzer" / "models"
    models.mkdir(parents=True)
    (models / settings.LEGACY_HF_FILENAME).write_bytes(b"x")
    path = tmp_path / "settings.json"
    path.write_text('{"hf_filename": "%s"}' % settings.LEGACY_HF_FILENAME, encoding="utf-8")
    assert settings.load_settings(path).hf_filename == settings.LEGACY_HF_FILENAME
