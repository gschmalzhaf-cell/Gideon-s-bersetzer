import threading

import pytest
import requests

from gideons_uebersetzer import model_manager


class FakeResponse:
    def __init__(self, status_code, chunks, headers=None):
        self.status_code = status_code
        self._chunks = chunks
        self.headers = headers or {}
        self.closed = False

    def iter_content(self, chunk_size):
        yield from self._chunks

    def close(self):
        self.closed = True


def _patch(monkeypatch, size, data, support_range=True):
    monkeypatch.setattr(model_manager, "model_file_info", lambda repo, fn: {"url": "https://example.test/m.gguf", "size": size, "etag": "x"})
    calls = []

    def fake_get(url, headers=None, stream=False, timeout=None):
        calls.append(headers or {})
        range_header = (headers or {}).get("Range")
        if support_range and range_header:
            start = int(range_header.split("=")[1].rstrip("-"))
            return FakeResponse(206, [data[start:]])
        return FakeResponse(200, [data])

    monkeypatch.setattr(model_manager.requests, "get", fake_get)
    return calls


def test_download_writes_complete_file(monkeypatch, tmp_path):
    data = b"x" * 5000
    _patch(monkeypatch, 5000, data)
    progress = []
    dest = model_manager.download_model("repo", "m.gguf", tmp_path, progress_cb=lambda d, t, s: progress.append((d, t)))
    assert dest.read_bytes() == data
    assert not (tmp_path / "m.gguf.part").exists()
    assert progress[-1][0] == 5000


def test_download_resume_after_cancel(monkeypatch, tmp_path):
    data = b"y" * 4000
    calls = _patch(monkeypatch, 4000, data)
    plain_get = model_manager.requests.get
    cancel = threading.Event()

    class CancellingResponse(FakeResponse):
        def iter_content(self, chunk_size):
            yield data[:1000]
            cancel.set()
            yield data[1000:]

    def cancelling_get(url, headers=None, stream=False, timeout=None):
        calls.append(headers or {})
        return CancellingResponse(200, [data])

    monkeypatch.setattr(model_manager.requests, "get", cancelling_get)
    with pytest.raises(model_manager.DownloadCancelled):
        model_manager.download_model("repo", "m.gguf", tmp_path, cancel_event=cancel)
    part = tmp_path / "m.gguf.part"
    assert part.is_file() and part.stat().st_size == 1000

    # Fortsetzung per Range mit normalem Server-Verhalten
    monkeypatch.setattr(model_manager.requests, "get", plain_get)
    calls.clear()
    cancel.clear()
    dest = model_manager.download_model("repo", "m.gguf", tmp_path, cancel_event=cancel)
    assert dest.read_bytes() == data
    assert any("Range" in c for c in calls)


def test_download_insufficient_space(monkeypatch, tmp_path):
    monkeypatch.setattr(model_manager, "model_file_info", lambda r, f: {"url": "https://example.test/m", "size": 10**12, "etag": "e"})
    monkeypatch.setattr(model_manager, "free_space_bytes", lambda p: 10**9)
    with pytest.raises(model_manager.ModelError, match="nicht genug Speicherplatz"):
        model_manager.download_model("repo", "m.gguf", tmp_path)


def test_delete_model_frees_space(tmp_path):
    p = tmp_path / "m.gguf"
    p.write_bytes(b"z" * 100)
    freed = model_manager.delete_model(p)
    assert freed == 100
    assert model_manager.model_disk_usage(p) == 0
    assert not model_manager.is_model_present(p)


def test_format_bytes():
    assert model_manager.format_bytes(2048) == "2.0 KiB"
    assert "GiB" in model_manager.format_bytes(4.4 * 1024**3)
