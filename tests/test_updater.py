import threading

import pytest
import requests

from gideons_uebersetzer import updater


def test_parse_version_and_is_newer():
    assert updater.parse_version("v1.2.3") == (1, 2, 3)
    assert updater.parse_version("1.10.0") == (1, 10, 0)
    assert updater.is_newer("1.2.0", "1.1.9")
    assert not updater.is_newer("1.1.5", "1.1.5")
    assert not updater.is_newer("1.1.4", "1.1.5")
    assert updater.is_newer("2.0.0", "1.99.99")


class FakeResp:
    def __init__(self, status_code=200, data=None, text="", headers=None, chunks=None):
        self.status_code = status_code
        self._data = data
        self.text = text
        self.headers = headers or {}
        self._chunks = chunks or []
        self.closed = False

    def json(self):
        return self._data

    def iter_content(self, chunk_size):
        yield from self._chunks

    def close(self):
        self.closed = True


RELEASE_JSON = {
    "tag_name": "v9.9.9",
    "assets": [
        {"name": "Tolino-Uebersetzer-Setup-9.9.9.exe", "browser_download_url": "https://x/9.9.9.exe"},
        {"name": "Tolino-Uebersetzer-Setup-9.9.8.exe", "browser_download_url": "https://x/9.9.8.exe"},
        {"name": "notes.txt", "browser_download_url": "https://x/notes.txt"},
    ],
}


def test_latest_release_picks_newest_installer_asset(monkeypatch):
    monkeypatch.setattr(updater.requests, "get", lambda *a, **k: FakeResp(200, RELEASE_JSON))
    rel = updater.latest_release()
    assert rel["version"] == "9.9.9"
    assert rel["asset_name"] == "Tolino-Uebersetzer-Setup-9.9.9.exe"
    assert rel["asset_url"] == "https://x/9.9.9.exe"


def test_latest_release_http_error(monkeypatch):
    monkeypatch.setattr(updater.requests, "get", lambda *a, **k: FakeResp(404, text="not found"))
    with pytest.raises(updater.UpdateError, match="404"):
        updater.latest_release()


def test_check_for_update(monkeypatch):
    monkeypatch.setattr(updater, "latest_release", lambda: {"version": "99.0.0", "asset_name": "x.exe", "asset_url": "u"})
    assert updater.check_for_update() is not None
    monkeypatch.setattr(updater, "latest_release", lambda: {"version": "0.0.1", "asset_name": "x.exe", "asset_url": "u"})
    assert updater.check_for_update() is None


def test_download_installer_writes_file(monkeypatch, tmp_path):
    data = b"i" * 5000

    def fake_get(url, headers=None, stream=False, timeout=None):
        assert stream
        return FakeResp(200, headers={"Content-Length": str(len(data))}, chunks=[data[:2000], data[2000:]])

    monkeypatch.setattr(updater.requests, "get", fake_get)
    progress = []
    dest = updater.download_installer(
        "https://x/Tolino-Uebersetzer-Setup-9.9.9.exe",
        tmp_path,
        asset_name="Tolino-Uebersetzer-Setup-9.9.9.exe",
        progress_cb=lambda d, t, s: progress.append((d, t)),
    )
    assert dest.name == "Tolino-Uebersetzer-Setup-9.9.9.exe"
    assert dest.read_bytes() == data
    assert not (tmp_path / (dest.name + ".part")).exists()
    assert progress[-1][0] == 5000


def test_download_installer_resume_and_cancel(monkeypatch, tmp_path):
    data = b"r" * 4000
    part = tmp_path / "Tolino-Uebersetzer-Setup-9.9.9.exe.part"
    part.write_bytes(data[:1000])

    def fake_get(url, headers=None, stream=False, timeout=None):
        range_header = (headers or {}).get("Range")
        if range_header:
            start = int(range_header.split("=")[1].rstrip("-"))
            return FakeResp(206, headers={"Content-Length": str(len(data) - start)}, chunks=[data[start:]])
        return FakeResp(200, headers={"Content-Length": str(len(data))}, chunks=[data])

    monkeypatch.setattr(updater.requests, "get", fake_get)
    dest = updater.download_installer(
        "https://x/Tolino-Uebersetzer-Setup-9.9.9.exe", tmp_path,
        asset_name="Tolino-Uebersetzer-Setup-9.9.9.exe",
    )
    assert dest.read_bytes() == data

    dest.unlink()
    part.write_bytes(b"z" * 10)
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(updater.UpdateCancelled):
        updater.download_installer(
            "https://x/Tolino-Uebersetzer-Setup-9.9.9.exe", tmp_path,
            asset_name="Tolino-Uebersetzer-Setup-9.9.9.exe", cancel_event=cancel,
        )


def test_download_installer_http_error(monkeypatch, tmp_path):
    monkeypatch.setattr(updater.requests, "get", lambda *a, **k: FakeResp(403, text="forbidden"))
    with pytest.raises(updater.UpdateError, match="403"):
        updater.download_installer("https://x/a.exe", tmp_path)
