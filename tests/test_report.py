from gideons_uebersetzer import report, settings as settings_mod
from gideons_uebersetzer.cache import STATUS_DONE, STATUS_FAILED, TranslationCache


def test_report_redacts_api_key_and_contains_sections(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    s = settings_mod.Settings(api_key="SECRET-KEY", output_dir=str(tmp_path))
    text = report.build_report(s, log_lines=["Seite 1/9: OCR …", "Abschnitt 3 fehlgeschlagen (X)"])
    assert "SECRET-KEY" not in text
    assert '"api_key": "***"' in text
    assert "Diagnose-Report" in text
    assert "Seite 1/9: OCR" in text
    assert "Qwen2.5-7B-Instruct-Q4_K_M.gguf" in text
    assert "Maschinenlesbarer Anhang" in text


def test_report_includes_failed_cache_chunks(tmp_path, monkeypatch, sample_pdf):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    cache = TranslationCache(sample_pdf, TranslationCache.cache_file_for(sample_pdf), tool="offline")
    cache.record(0, "The quick brown fox …", "Der Fuchs …", STATUS_DONE)
    cache.record(1, "Another english paragraph here.", "", STATUS_FAILED, problem="Der Text wirkt nicht übersetzt.")
    s = settings_mod.Settings(output_dir=str(tmp_path))
    text = report.build_report(s)
    assert "Der Text wirkt nicht übersetzt." in text
    assert "Another english paragraph here." in text
    assert "1 ok, 1 fehlgeschlagen" in text


def test_write_report_creates_markdown_file(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    s = settings_mod.Settings(output_dir=str(tmp_path))
    path = report.write_report(s)
    assert path.is_file() and path.suffix == ".md"
    assert "Diagnose-Report" in path.read_text(encoding="utf-8")


def test_cache_problem_roundtrip(tmp_path, monkeypatch, sample_pdf):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    cache = TranslationCache(sample_pdf, TranslationCache.cache_file_for(sample_pdf), tool="offline")
    cache.record(2, "Source text", "", STATUS_FAILED, problem="leer")
    loaded = TranslationCache.load(sample_pdf)
    assert loaded is not None and loaded.get(2).problem == "leer"


def test_log_buffer_is_capped():
    report.LOG_BUFFER.clear()
    for i in range(report.LOG_BUFFER_MAX + 50):
        report.add_log_line(f"line {i}")
    assert len(report.LOG_BUFFER) == report.LOG_BUFFER_MAX
    assert report.LOG_BUFFER[-1] == f"line {report.LOG_BUFFER_MAX + 49}"
