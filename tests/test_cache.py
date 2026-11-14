from gideons_uebersetzer.cache import STATUS_DONE, STATUS_FAILED, TranslationCache


def test_cache_roundtrip_and_resume(tmp_path, sample_pdf):
    cache_file = TranslationCache.cache_file_for(sample_pdf, tmp_path / "cache")
    cache = TranslationCache(sample_pdf, cache_file, tool="offline")
    cache.record(0, "Hello world", "Hallo Welt", STATUS_DONE)
    cache.record(1, "Bye", "Tschüss", STATUS_FAILED)

    loaded = TranslationCache.load(sample_pdf, base_dir=tmp_path / "cache")
    assert loaded is not None
    assert loaded.get(0).translation == "Hallo Welt"
    assert loaded.get(0).status == STATUS_DONE
    assert loaded.get(1).status == STATUS_FAILED
    assert loaded.done_count == 1
    assert loaded.failed_count == 1
    assert loaded.matches(["Hello world", "Bye"])
    assert not loaded.matches(["Hello world", "Anderer Text"])


def test_cache_file_is_stable_per_source(tmp_path, sample_pdf):
    a = TranslationCache.cache_file_for(sample_pdf, tmp_path)
    b = TranslationCache.cache_file_for(sample_pdf, tmp_path)
    assert a == b
    assert a.suffix == ".json"


def test_cache_clear(tmp_path, sample_pdf):
    cache = TranslationCache(sample_pdf, tmp_path / "c.json")
    cache.record(0, "a", "b", STATUS_DONE)
    assert cache.cache_file.is_file()
    cache.clear()
    assert not cache.cache_file.exists()
