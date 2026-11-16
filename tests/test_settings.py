import re

from gideons_uebersetzer import settings


def test_default_hf_model_is_qwen25_7b():
    assert settings.DEFAULT_HF_REPO == "bartowski/Qwen2.5-7B-Instruct-GGUF"
    assert settings.DEFAULT_HF_FILENAME == "Qwen2.5-7B-Instruct-Q4_K_M.gguf"
    assert re.fullmatch(r"Qwen2\.5-7B-Instruct-Q\d_K_\w+\.gguf", settings.DEFAULT_HF_FILENAME)


def test_default_model_path_prefers_new_file(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    models = tmp_path / "Tolino-Uebersetzer" / "models"
    models.mkdir(parents=True)
    (models / settings.DEFAULT_HF_FILENAME).write_bytes(b"x")
    for name in settings.LEGACY_HF_FILENAMES:
        (models / name).write_bytes(b"x")
    assert settings.default_model_path().name == settings.DEFAULT_HF_FILENAME


def test_default_model_path_falls_back_to_legacy_file(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    models = tmp_path / "Tolino-Uebersetzer" / "models"
    models.mkdir(parents=True)
    (models / settings.LEGACY_HF_FILENAMES[0]).write_bytes(b"x")
    assert settings.default_model_path().name == settings.LEGACY_HF_FILENAMES[0]


def test_load_settings_resets_legacy_filename_when_file_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    path = tmp_path / "settings.json"
    path.write_text('{"hf_filename": "%s"}' % settings.LEGACY_HF_FILENAMES[1], encoding="utf-8")
    assert settings.load_settings(path).hf_filename == settings.DEFAULT_HF_FILENAME


def test_load_settings_keeps_legacy_filename_when_file_present(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    models = tmp_path / "Tolino-Uebersetzer" / "models"
    models.mkdir(parents=True)
    (models / settings.LEGACY_HF_FILENAMES[0]).write_bytes(b"x")
    path = tmp_path / "settings.json"
    path.write_text('{"hf_filename": "%s"}' % settings.LEGACY_HF_FILENAMES[0], encoding="utf-8")
    assert settings.load_settings(path).hf_filename == settings.LEGACY_HF_FILENAMES[0]


def test_load_settings_normalizes_ocr_backend(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    path = tmp_path / "settings.json"
    path.write_text('{"ocr_backend": "kaputt"}', encoding="utf-8")
    assert settings.load_settings(path).ocr_backend == "local"


def test_effective_ocr_backend():
    s = settings.Settings(ocr_backend="mistral")
    assert s.effective_ocr_backend("api", True) == "mistral"
    assert s.effective_ocr_backend("api", False) == "local"
    assert s.effective_ocr_backend("offline", True) == "local"
    s2 = settings.Settings(ocr_backend="local")
    assert s2.effective_ocr_backend("api", True) == "local"
